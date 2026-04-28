import base64
import os
import json
import uuid
from io import BytesIO
from typing import List, Dict, Any
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter
import re

from mistralai import Mistral, JSONSchema, ResponseFormat
from PIL import Image

from langchain_core.documents import Document as LCDocument
from langchain_openai import ChatOpenAI

from .utils.document_parser_utils import (
    clean_headers_footers,
    get_headers_and_footers,
)
from ...config.config import CONTEXT_SUMMARIZATION_MODEL, MISTRAL_API_KEY
from ...utils.logger import get_logger


class DocumentParserOCR:
    """
    This is the class containing the Mistral OCR parsing and chunking methods.
    Uses Mistral's OCR API for document parsing instead of Docling.
    """

    def __init__(self, default_lang: str = ""):
        self.logger = get_logger(__name__)
        self.header_chunker = MarkdownHeaderTextSplitter(
    headers_to_split_on = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
    ("####", "Header 4"),
]
, strip_headers=False
)
        self.text_chunker = RecursiveCharacterTextSplitter(
            chunk_size=256,
            chunk_overlap=30,
        )
        api_key = MISTRAL_API_KEY
        if not api_key:
            raise ValueError("MISTRAL_API_KEY environment variable is not set")
        
        self.client = Mistral(api_key=api_key)
        self.summary_llm = ChatOpenAI(model=CONTEXT_SUMMARIZATION_MODEL)
        
        # Define the JSON schema for bbox annotations
        self.bbox_annotation_format = ResponseFormat(
            type="json_schema",
            json_schema=JSONSchema(
                name="response_schema",
                schema_definition={
                    "properties": {
                        "description": {
                            "description": "describe the image",
                            "type": "string"
                        },
                        "text": {
                            "description": "the text contained inside the image",
                            "type": "string"
                        }
                    },
                    "required": [
                        "description",
                        "text"
                    ],
                    "type": "object"
                },
            ),
        )
        
        self.logger.info("DocumentParserOCR correctly initialized")

    def encode_file(self, file_path: str) -> str:
        """
        Encode a file to base64 string.
        """
        with open(file_path, "rb") as pdf_file:
            return base64.b64encode(pdf_file.read()).decode('utf-8')

    def build_doc_context_llm(self, text: str, max_chars: int = 2000) -> str:
        """
        Generates a one sentence summary of the document.
        """
        snippet = text[:max_chars]
        # Remove annotation tags and their content
        snippet = re.sub(r'<annotation>.*?</annotation>', '', snippet, flags=re.DOTALL)
        prompt = (
            "In one concise sentence, describe what this document is mainly about, including all the keywords. Do not write any introductory text just write the answer. \n"
            f"{snippet}"
        )
        resp = self.summary_llm.invoke(prompt)
        summary = resp.content.strip()
        return summary[:max_chars]

    def extract_and_store_images(self, ocr_response, parent_doc_id: str):
        """
        Extract and store images from OCR response.
        Extracts Base64 images from the OCR response and formats them to be uploaded to mongo.
        
        OCRImageObject structure:
        - id: str (Image ID)
        - image_base64: Optional[str] (Base64 encoded image)
        - image_annotation: Optional[str] (Annotation in JSON)
        - top_left_x, top_left_y, bottom_right_x, bottom_right_y: coordinates
        """
        image_ids = []
        assets = []
        image_id_mapping = {}  # Maps original image IDs to new API URLs

        if hasattr(ocr_response, 'pages') and ocr_response.pages:
            for page in ocr_response.pages:
                if hasattr(page, 'images') and page.images:
                    for image in page.images:
                        # Get the image ID from the OCR response
                        original_image_id = image.id
                        
                        # Check if image has base64 data
                        if hasattr(image, 'image_base64') and image.image_base64:
                            try:
                                # Handle data URI prefix if present (e.g., "data:image/jpeg;base64,")
                                base64_data = image.image_base64
                                if ',' in base64_data:
                                    base64_data = base64_data.split(',', 1)[1]
                                
                                # Decode base64 and convert to PIL Image, then save as PNG
                                # This matches document_parser_service.py approach for consistent format
                                raw_bytes = base64.b64decode(base64_data)
                                pil_img = Image.open(BytesIO(raw_bytes))
                                
                                buf = BytesIO()
                                pil_img.save(buf, format="JPEG")
                                img_bytes = buf.getvalue()
                                
                                asset_id = str(uuid.uuid4())
                                
                                asset_doc = {
                                    "_id": asset_id,
                                    "parent_doc_id": parent_doc_id,
                                    "mime_type": "image/JPEG",
                                    "data": img_bytes,
                                    "kind": "picture",
                                }
                                
                                # Map the original image ID to the new API URL
                                image_id_mapping[original_image_id] = f"/api/images/{asset_id}"
                                
                                image_ids.append(asset_id)
                                assets.append(asset_doc)
                            except Exception as e:
                                self.logger.warning(f"Failed to process image {original_image_id}: {str(e)}")
                                continue

        return image_ids, assets, image_id_mapping

    def process_ocr_response_images(self, ocr_response, parent_doc_id: str):
        """
        Extract image attributes, store images, and return processed markdown per page.
        
        Returns:
            image_ids: List of stored image asset IDs
            assets: List of asset documents for MongoDB
            processed_pages: Dict mapping page index to processed markdown with image URLs and annotations
        """
        image_ids = []
        assets = []
        processed_pages = {}  # page_index -> processed markdown
        
        if not hasattr(ocr_response, 'pages') or not ocr_response.pages:
            return image_ids, assets, processed_pages
        
        for page in ocr_response.pages:
            page_idx = page.index
            image_id_mapping = {}  # Maps original image IDs to new API URLs for this page
            image_annotations = {}  # Maps original image IDs to their annotations
            
            if hasattr(page, 'images') and page.images:
                for image in page.images:
                    original_image_id = image.id
                    
                    # Extract annotation if available
                    if hasattr(image, 'image_annotation') and image.image_annotation:
                        annotation = image.image_annotation
                        if isinstance(annotation, str):
                            try:
                                annotation = json.loads(annotation)
                            except json.JSONDecodeError:
                                annotation = {"text": annotation}
                        image_annotations[original_image_id] = annotation
                    
                    # Store image if base64 data exists
                    if hasattr(image, 'image_base64') and image.image_base64:
                        try:
                            # Handle data URI prefix if present (e.g., "data:image/jpeg;base64,")
                            base64_data = image.image_base64
                            if ',' in base64_data:
                                base64_data = base64_data.split(',', 1)[1]
                            
                            # Decode base64 and convert to PIL Image, then save as PNG
                            # This matches document_parser_service.py approach for consistent format
                            raw_bytes = base64.b64decode(base64_data)
                            pil_img = Image.open(BytesIO(raw_bytes))
                            
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
                            
                            image_id_mapping[original_image_id] = f"/api/images/{asset_id}"
                            image_ids.append(asset_id)
                            assets.append(asset_doc)
                        except Exception as e:
                            self.logger.warning(f"Failed to process image {original_image_id}: {str(e)}")
                            continue
            
            # Process markdown for this page (images first)
            page_md = page.markdown or ""
            
            for original_id, api_url in image_id_mapping.items():
                annotation = image_annotations.get(original_id, {})
                description = annotation.get("description", "")
                text_content = annotation.get("text", "")
                
                # Build replacement with annotation
                if description or text_content:
                    annotation_text = ""
                    if description:
                        annotation_text += f"\n\n*{description}*"
                    if text_content:
                        annotation_text += f"\n\n{text_content}"
                    image_replacement = f"![Image]({api_url})<annotation>{annotation_text}</annotation>"
                else:
                    image_replacement = f"![Image]({api_url})"
                
                page.markdown = page.markdown.replace(f"![{original_id}]", image_replacement)
                page.markdown = page.markdown.replace(original_id, api_url)

            # Insert tables into markdown for parsed output (do not mutate page.markdown for tables)
            page_md = page.markdown or ""
            table_id_to_content = {}
            if hasattr(page, 'tables') and page.tables:
                for table in page.tables:
                    table_id_to_content[table.id] = table.content

            for table_id, table_content in table_id_to_content.items():
                page_md = page_md.replace(f"![{table_id}]", table_content)
                page_md = page_md.replace(f"[{table_id}]", table_content)
            
            processed_pages[page_idx] = page_md
        
        return image_ids, assets, processed_pages
    

    def ocr_process_document(self, file_path: str, table_format: str = "markdown"):
        """
        Process a document using Mistral OCR API.
        
        Args:
            file_path: Path to the PDF file
            table_format: Format for table extraction - "html" or "markdown"
        """
        base64_file = self.encode_file(file_path)
        
        ocr_response = self.client.ocr.process(
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{base64_file}"
            },
            model="mistral-ocr-latest",
            include_image_base64=True,
            table_format=table_format,
            #bbox_annotation_format=self.bbox_annotation_format
        )
        
        return ocr_response

    def ocr_response_to_markdown(self, ocr_response) -> str:
        """
        Convert OCR response to markdown format.
        
        OCRResponse structure:
        - pages: List[OCRPageObject]
          - index: int (page index starting from 0)
          - markdown: str (the markdown content of the page)
          - images: List[OCRImageObject]
            - id: str (image ID)
            - image_base64: Optional[str]
          - tables: List[OCRTableObject] (optional, stored separately)
            - id: str (table ID, referenced in markdown)
            - content: str (table content in specified format - HTML or markdown)
            - format_: Format
        
        Tables are stored in a separate list and need to be inserted into the markdown
        at the location where their ID is referenced.
        """
        markdown_parts = []
        
        if hasattr(ocr_response, 'pages') and ocr_response.pages:
            for page in ocr_response.pages:
                page_md = page.markdown or ""
                
                # Build a mapping of table IDs to their content
                table_id_to_content = {}
                if hasattr(page, 'tables') and page.tables:
                    for table in page.tables:
                        table_id_to_content[table.id] = table.content
                
                # Replace table references with actual table content
                # Mistral OCR references tables in markdown using their IDs
                for table_id, table_content in table_id_to_content.items():
                    # Try different reference patterns that Mistral might use
                    # Pattern 1: ![table_id] or [table_id]
                    page_md = page_md.replace(f"![{table_id}]", table_content)
                    page_md = page_md.replace(f"[{table_id}]", table_content)
                
                
                if page_md:
                    markdown_parts.append(page_md)
        
        return "\n\n".join(markdown_parts)

    
    def parse_to_md(
        self, document: Dict[str, Any], include_images: bool = True, remove_artifacts: bool = True
    ):
        """
        Parse PDF into markdown using Mistral OCR, update the document, and return it.
        """
        input_doc_path = document["local_path"]
        
        self.logger.info(f"Processing document with Mistral OCR: {input_doc_path}")
        
        # Process document with Mistral OCR
        ocr_response = self.ocr_process_document(input_doc_path)
        
        if include_images:
            image_ids, assets, processed_pages = self.process_ocr_response_images(
                ocr_response, document["_id"]
            )
            
            document["image_ids"] = image_ids
            document["assets"] = assets
            
            # Build markdown from processed pages (with image URLs replaced)
            md = "\n\n".join(processed_pages[idx] for idx in sorted(processed_pages.keys()))
        else:
            md = self.ocr_response_to_markdown(ocr_response)

        # Remove artifacts (headers, footers, confidential text, etc.)
        if remove_artifacts:
            document["parsed"] = clean_headers_footers(
                md, get_headers_and_footers(document["local_path"])
            )
        else:
            document["parsed"] = md

        self.logger.info("Building document context with LLM...")
        # Generate the context for the whole doc
        document["context"] = self.build_doc_context_llm(md)
        
        self.logger.info("parse_to_md: Document parsed correctly with Mistral OCR")
        return document, ocr_response

    def hierarchical_chunking(
        self,
        ocr_response,
        base_metadata: Dict[str, Any] = {},
    ) -> List[LCDocument]:
        """
        Build chunks as langchain documents using hierarchical chunking.
        """
        lc_docs = []
        chunker = self.header_chunker
        text_splitter = self.text_chunker
        
        # Build full markdown and collect tables
        md = ""
        tables = []

        for page in ocr_response.pages:
            if hasattr(page, 'markdown') and page.markdown:
                md += page.markdown + "\n\n"
            if hasattr(page, 'tables') and page.tables:
                for table in page.tables:
                    tables.append(table)
        
        # Split by headers then by size
        md_header_splits = chunker.split_text(md)
        splits = text_splitter.split_documents(md_header_splits)

        for i, chunk in enumerate(splits):
            text = chunk.page_content
            bm25_text = text
            
            # Replace table references with actual table content
            for table in tables:
                if f"![{table.id}]" in bm25_text or f"[{table.id}]" in bm25_text:
                    bm25_text = bm25_text.replace(f"![{table.id}]", table.content)
                    bm25_text = bm25_text.replace(f"[{table.id}]", table.content)
                        
            # Build bm25_text with context and full text including tables
            bm25_contextful_text = " ".join(
                filter(
                    None,
                    [
                        base_metadata.get("context", ""),
                        bm25_text,
                    ],
                )
            )
            
            meta = {
                **base_metadata,
                "chunk_index": i,
                "bm25_text": bm25_contextful_text,
                "embed_text": text,
                "original_text": bm25_text
            }
            
            lc_docs.append(LCDocument(page_content=text, metadata=meta))
        
        return lc_docs


            
