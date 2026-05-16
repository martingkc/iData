
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Any
import uuid
import gc
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem
from langchain_core.documents import Document as LCDocument
from langchain_openai import ChatOpenAI
from docling_core.types.doc import RefItem, TextItem, DocItemLabel
from docling_core.types.doc import TableItem
from ..document_parser.utils.document_parser_utils import (
    clean_headers_footers,
    get_headers_and_footers,
)
from ...config.config import CONTEXT_SUMMARIZATION_MODEL, LMSTUDIO_BASE_URL, OPENAI_API_KEY
from ...utils.logger import get_logger
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend



class DocumentParser:
    """
    This is the class containing the Docling parsing and chunking methods.

    """

    def __init__(self, default_lang: str = ""):
        self.logger = get_logger(__name__)
        self.chunker = HybridChunker(
            max_tokens=512, # this is the max token limit for embeddings-small 
            min_tokens=80,
            respect_structure=True,
        )
        # ====== STD pipeline options ======
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.do_cell_matching = True
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=4,  # Reduced from 10 to prevent OOM
            device=AcceleratorDevice.AUTO,
        )
        pipeline_options.images_scale = 1.5  # Reduced from 2.0 to lower memory usage
        pipeline_options.generate_page_images = False  # Disabled to reduce memory
        pipeline_options.generate_picture_images = True

        if default_lang:
            pipeline_options.ocr_options.lang = [default_lang]

        self.doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options, backend=PyPdfiumDocumentBackend )
            }
        )

        self.summary_llm = ChatOpenAI( base_url=LMSTUDIO_BASE_URL, api_key=OPENAI_API_KEY)

        self.logger.info("DocumentParser correctly initialized")

    def build_doc_context_llm(self, text: str, max_chars: int = 3000) -> str:
        """
        Generates a one sentence summary of the document
        """
        snippet = text[:max_chars]
        prompt = (
            "In one concise sentence, describe what this document is mainly about, including all the keywords. Do not write any introductory text just write the answer. \n"
            f"{snippet}"
        )
        resp = self.summary_llm.invoke(prompt)
        summary = resp.content.strip()
        return summary[:max_chars]

    def get_picture_texts(self, dl_doc, picture_ref_to_uri):
        picture_texts = {}  # {picture_uri: [text_items]}
        for text_item in dl_doc.texts:
            if hasattr(text_item, "parent") and text_item.parent:
                parent_ref = text_item.parent.cref  # '#/pictures/0' or '#/body'
                # Only process texts that are children of pictures, skip body texts
                if parent_ref in picture_ref_to_uri:
                    image_uri = picture_ref_to_uri[parent_ref]
                    if image_uri not in picture_texts:
                        picture_texts[image_uri] = []
                    picture_texts[image_uri].append(text_item.text)
        return picture_texts

    def append_picture_texts_to_md(self, md, picture_texts):
        for image_uri, texts in picture_texts.items():
            if image_uri in md:
                ocr_text = " ".join(texts)
                md = md.replace(image_uri, f"{image_uri}\n\n{ocr_text}")
        return md

    def get_text_groups_under_pictures(self, dl_doc):
        picture_text_groups = {}
        for text_item in dl_doc.texts:
            if hasattr(text_item, "parent") and text_item.parent:
                parent_ref = text_item.parent.cref
                if parent_ref and parent_ref.startswith("#/pictures/"):
                    if parent_ref not in picture_text_groups:
                        picture_text_groups[parent_ref] = []
                    picture_text_groups[parent_ref].append(text_item)
        return picture_text_groups

    def merge_texts_under_pictures(self, dl_doc, picture_text_groups):
        merged_texts = []
        # merged_tables = []
        texts_to_remove = set()
        # text indicy karisiyor get max yap
        max_text_idx = max(
            (
                int(t.self_ref.split("/")[-1])
                for t in dl_doc.texts
                if t.self_ref.startswith("#/texts/")
            ),
            default=1,
        )
        text_idx_counter = 1 + max_text_idx
        # max_table_idx = max(
        #     (int(t.self_ref.split('/')[-1]) for t in dl_doc.texts
        #     if t.self_ref.startswith('#/tables/')),default=1)
        text_idx_counter = 1 + max_text_idx
        # table_idx_counter = 1 + max_table_idx

        for picture_ref, text_items in picture_text_groups.items():
            if not text_items:
                continue
            # Mark all original text items for removal
            for item in text_items:
                texts_to_remove.add(item.self_ref)
            # Merge all text content
            merged_text = " ".join(item.text for item in text_items if item.text)
            # Create a new merged TextItem based on the first item's properties
            first_item = text_items[0]
            # labels_in_tables="|-"

            # if bool(set(labels_in_tables) & set(merged_text)):
            #         merged_item =TableItem(
            #         self_ref=f"#/tables/{table_idx_counter}",
            #         parent=RefItem(cref=dl_doc.body.self_ref),  # Set parent to body from the start
            #         children=[],
            #         content_layer=first_item.content_layer,
            #         meta=first_item.meta,
            #         label=DocItemLabel.TEXT,
            #         prov=[],  # Empty provenance to avoid path resolution issues
            #         text=merged_text,
            #         orig=merged_text,
            #         formatting=None,
            #         hyperlink=None
            #     )
            #         table_idx_counter += 1
            #         merged_tables.append(merged_item)

            # else:
            merged_item = TextItem(
                self_ref=f"#/texts/{text_idx_counter}",
                parent=RefItem(
                    cref=dl_doc.body.self_ref
                ),  # Set parent to body from the start
                children=[],
                content_layer=first_item.content_layer,
                meta=first_item.meta,
                label=DocItemLabel.TEXT,
                prov=[],  # Empty provenance to avoid path resolution issues
                text=merged_text,
                orig=merged_text,
                formatting=None,
                hyperlink=None,
            )
            text_idx_counter += 1
            merged_texts.append(merged_item)
        return merged_texts  # , merged_tables

    def prepare_dl_doc(self, dl_doc):
        picture_text_groups = self.get_text_groups_under_pictures(dl_doc)
        merged_texts = self.merge_texts_under_pictures(dl_doc, picture_text_groups)
        dl_doc.texts.extend(merged_texts)
        if merged_texts and dl_doc.body:
            for merged_item in merged_texts:
                text_ref = RefItem(cref=merged_item.self_ref)
                dl_doc.body.children.append(text_ref)
        # if merged_tables and dl_doc.body:
        #     for merged_item in merged_tables:
        #         table_ref = RefItem(cref=merged_item.self_ref)
        #         dl_doc.body.children.append(table_ref)
        return dl_doc

    def extract_and_store_images(self, dl_doc, parent_doc_id):
        """
        Extract and store images. This is done so that images can be stored on mongo.
        So this fetches the Base64 Image saves it as a file and formats it to be uploaded to mongo.

        """
        image_ids = []
        assets = []
        picture_ref_to_uri = {}

        for element, _level in dl_doc.iterate_items():
            if not isinstance(element, PictureItem):
                continue

            pil_img = element.get_image(dl_doc)
            if pil_img is None:
                continue

            buf = BytesIO()
            pil_img.save(buf, format="PNG")
            img_bytes = buf.getvalue()

            asset_id = str(uuid.uuid4())

            asset_doc = {
                "_id": asset_id,
                "parent_doc_id": parent_doc_id,
                "mime_type": "image/png",
                "data": img_bytes,
                "kind": "picture",
            }

            if element.image is not None:
                element.image.uri = f"/api/images/{asset_id}"
                picture_ref_to_uri[element.self_ref] = (
                    f"![Image](/api/images/{asset_id})"
                )

            image_ids.append(asset_id)
            assets.append(asset_doc)
        return image_ids, assets, picture_ref_to_uri

    def parse_to_md(
        self, document, include_images: bool = True, remove_artifacts: bool = True
    ):
        """
        Parse PDF into markdown, update the document, and return it.
        """
        input_doc_path = Path(document["local_path"])
        conv_result = self.doc_converter.convert(input_doc_path, page_range=[1,100])
        dl_doc = conv_result.document

        if include_images:
            image_ids, assets, picture_ref_to_uri = self.extract_and_store_images(
                dl_doc,
                parent_doc_id=document["_id"],
            )

            document["image_ids"] = image_ids
            document["assets"] = assets
            picture_texts = self.get_picture_texts(dl_doc, picture_ref_to_uri)
            md = dl_doc.export_to_markdown(image_mode=ImageRefMode.REFERENCED)
            md = self.append_picture_texts_to_md(md, picture_texts)
        else:
            md = dl_doc.export_to_markdown(strict_text=True)

        # Remove_artifacts removes any (CONFIDENTIAL or header, footer text which normally adds a shit load of noise)
        if remove_artifacts:
            document["parsed"] = clean_headers_footers(
                md, get_headers_and_footers(document["local_path"])
            )
        else:
            document["parsed"] = md

        self.logger.info("Building document context with LLM...")
        # Generate the context for the whole doc
        document["context"] = self.build_doc_context_llm(md)
        dl_doc = self.prepare_dl_doc(dl_doc)
        self.logger.info("parse_to_md: Document parsed correctly")
        return document, dl_doc

    def _strip_tables_using_items(self, chunk, text: str) -> str:
        """
        Remove the textual content of TableItem objects from the given text.
        Practically it iterates over the items that compose the chunks and checks if an item is a Table
        if so it removes it from the final text.
        """
        items = getattr(chunk.meta, "doc_items", []) or []
        table_items = [item for item in items if isinstance(item, TableItem)]

        cleaned = text
        for table in table_items:
            table_text = getattr(table, "text_content", None) or getattr(
                table, "text", None
            )
            if not table_text:
                continue

            cleaned = cleaned.replace(table_text.strip(), "")

        return cleaned.strip()

    def hierarchical_chunking(
        self,
        dl_doc,
        base_metadata={},
    ):
        """
        Build chunks as langchain documents using Docling's hierarchical chunker.
        Filters out small chunks that don't provide meaningful context.

        Possible chunk types are:
        - Text only: these just get embedded.
        - Table only: these get just processed using BM25.
        - Mixed: table text is removed from the embedding text, but kept in bm25_text.

        KISACA: karisik chunklarin embedlenen texti tablesiz ama tablelar BM25 ile
        endeksleniyor ve final chunkta table verisi kaliyor.
        Bu kod inanilmaz karisik ve anlasilmasi biraz zor. Direkt bana sor.
        """

        lc_docs = []
        chunker = self.chunker
        min_chunk_length = 100

        for chunk_idx, chunk in enumerate(chunker.chunk(dl_doc)):
            text = (chunk.text or "").strip()
            original_text = text
            items = getattr(chunk.meta, "doc_items", []) or []

            contains_table = any(isinstance(item, TableItem) for item in items)
            is_table_chunk = contains_table and all(
                isinstance(item, TableItem) for item in items
            )

            if is_table_chunk:
                # Table chunk: no text for embeddings
                text = ""
            elif contains_table:
                # Mixed: remove table text from embedding text, keep full original for BM25
                text = self._strip_tables_using_items(chunk, original_text)

            # Skip empty or short chunks (UNLESS it is a pure table)
            if not is_table_chunk and (not text or len(text) < min_chunk_length):
                continue

            # Extract image references to be saved on Mongo
            # (AS stated in the func description this aint necessary since the images are already on mongo and referencing them on milvus doesnt add anything)
            chunk_image_ids = self._extract_image_ids_from_items(items)

            meta: Dict[str, Any] = {
                **base_metadata,
                "chunk_index": chunk_idx,
                "chunk_type": ("table" if is_table_chunk else "text"),
            }

            # bm25_text contains the original text (including tables, in case there are some specific terms in the table)
            meta["bm25_text"] = " ".join(
                filter(
                    None,
                    [
                        base_metadata.get("context", ""),
                        original_text,
                    ],
                )
            )
            meta["original_text"] = original_text

            if chunk_image_ids:
                meta["image_ids"] = chunk_image_ids

            # Extract page_no
            page_infos = getattr(chunk.meta, "page_infos", []) or []
            pages = [
                getattr(pi, "page_no", None)
                for pi in page_infos
                if hasattr(pi, "page_no")
            ]
            if pages:
                meta["pages"] = pages

            lc_docs.append(LCDocument(page_content=text, metadata=meta))

        return lc_docs

    def _extract_image_ids_from_items(self, items: List[Any]) -> List[str]:
        """
        Extract image IDs from parsed text.
        This function is not strictly necessary so ignore.
        """

        ids = []
        for item in items:
            if isinstance(item, (PictureItem, TableItem)):
                if hasattr(item, "image") and item.image is not None:
                    uri = str(item.image.uri)

                    if "/api/images/" in uri:
                        img_id = uri.split("/api/images/")[-1]
                        if img_id:
                            ids.append(img_id)

        return ids