import os
from typing import Optional, Dict, Any, List, Tuple
from langchain_community.document_compressors import FlashrankRerank
from langchain_milvus import BM25BuiltInFunction, Milvus
from langchain_core.documents import Document
from .lm_studio_embeddings import LMStudioEmbeddings
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever

from ...utils.logger import get_logger
from ...config.config import MILVUS_HOST, MILVUS_PORT

logger = get_logger(__name__)


class DocumentCatalogueConnector:
    """
    Milvus connector for the document_catalogue collection.
    Stores document-level metadata with hybrid BM25 + dense search over the context field.
    
    Each document in the catalogue contains:
    - document_id: MongoDB document ID
    - context: LLM-generated summary of the document (used for embedding + BM25)
    - local_path: Local file path
    - remote_path: Remote/original path
    - created: Creation timestamp
    - parsed: Parsed markdown content (stored but not indexed)
    - image_ids: List of image asset IDs
    - table_ids: List of table asset IDs
    """

    def __init__(
        self,
        embeddings=LMStudioEmbeddings(),
        uri: Optional[str] = None,
        collection_name: str = "document_catalogue",
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        self._embeddings = embeddings
        self._collection_name = collection_name
        self._builtin_function = BM25BuiltInFunction(
            input_field_names="bm25_text",
            output_field_names="sparse",
        )

        try:
            connection_args = self._construct_connection_args(uri, host, port)
            logger.info(f"DocumentCatalogueConnector: Connecting to Milvus with args: {connection_args}")

            self._vector_store = Milvus(
                embedding_function=embeddings,
                collection_name=collection_name,
                connection_args=connection_args,
                index_params=[
                    {
                        "index_type": "FLAT",
                        "metric_type": "COSINE",
                        "params": {},
                    },  # dense
                    {
                        "index_type": "SPARSE_INVERTED_INDEX",
                        "metric_type": "BM25",
                        "params": {},
                    },
                ],
                builtin_function=self._builtin_function,
                vector_field=["dense", "sparse"],
                text_field="bm25_text",
                enable_dynamic_field=True,
                auto_id=True,
                drop_old=False,
            )
            self._compressor = FlashrankRerank()

            logger.info(
                f"DocumentCatalogueConnector initialized with collection: {collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize DocumentCatalogueConnector: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def _construct_connection_args(
        uri: Optional[str],
        host: Optional[str],
        port: Optional[int],
    ) -> Dict[str, Any]:
        """Build Milvus connection args from provided or env values."""
        connection_args: Dict[str, Any] = {}

        if uri:
            connection_args["uri"] = uri
            return connection_args

        host = MILVUS_HOST
        port = MILVUS_PORT
        if host and port:
            connection_args["host"] = host
            connection_args["port"] = port
            connection_args["uri"] = f"http://{host}:{port}"
            return connection_args

        default_uri = os.getenv("MILVUS_DB_PATH", "./milvus_data.db")
        connection_args["uri"] = default_uri
        return connection_args

    def add_document(
        self,
        document_id: str,
        context: str,
        local_path: str = "",
        remote_path: str = "",
        created: str = "",
        parsed: str = "",
        image_ids: List[str] = None,
        table_ids: List[str] = None,
        extra_metadata: Dict[str, Any] = None,
    ) -> List[str]:
        """
        Add a single document to the catalogue.
        
        The context field is used for both:
        - Dense embeddings (semantic search)
        - BM25 sparse index (lexical search)
        
        Returns the Milvus IDs of the inserted document.
        """
        try:
            if not context:
                logger.warning(f"Document {document_id} has empty context, skipping catalogue entry")
                return []

            # Build metadata
            metadata = {
                "document_id": document_id,
                "local_path": local_path,
                "remote_path": remote_path,
                "created": created,
                "parsed": parsed[:50000] if parsed else "",  # Truncate large parsed content
                "image_ids": image_ids or [],
                "table_ids": table_ids or [],
                "kind": "document",
            }
            
            if extra_metadata:
                metadata.update(extra_metadata)

            # bm25_text = context (the summary)
            metadata["bm25_text"] = context

            # Create Document with context as page_content (for embedding)
            doc = Document(page_content=context, metadata=metadata)

            # Compute embedding from context
            vectors = self._embeddings.embed_documents([context])

            # Insert using add_embeddings
            result_ids = self._vector_store.add_embeddings(
                texts=[context],  # BM25 text field
                embeddings=vectors,
                metadatas=[metadata],
            )

            logger.info(f"Added document {document_id} to catalogue with id {result_ids}")
            return result_ids

        except Exception as e:
            logger.error(f"Error adding document {document_id} to catalogue: {str(e)}", exc_info=True)
            raise

    def search(
        self,
        query: str,
        k: int = 5,
        weights: Tuple[float, float] = (0.7, 0.3),
        expr: Optional[str] = None,
        rerank: bool = True,
    ) -> List[Document]:
        """
        Hybrid search (dense + BM25) over document catalogue.

        Parameters
        ----------
        query : str
            User query.
        k : int
            Number of results to return.
        weights : (dense_weight, sparse_weight)
            How much to trust embeddings vs BM25.
        expr : str, optional
            Milvus filter expression.
        rerank : bool
            Whether to use FlashRank reranking.
        """
        try:
            search_kwargs = {
                "k": k if not rerank else k * 2,
                "ranker_type": "weighted",
                "ranker_params": {"weights": list(weights)},
            }
            if expr:
                search_kwargs["expr"] = expr

            if not rerank:
                docs = self._vector_store.similarity_search(query, **search_kwargs)
            else:
                retriever = self._vector_store.as_retriever(search_kwargs=search_kwargs)
                compression_retriever = ContextualCompressionRetriever(
                    base_compressor=self._compressor,
                    base_retriever=retriever,
                )
                docs = compression_retriever.invoke(query)[:k]

            return docs
        except Exception as e:
            logger.error(f"Error searching document catalogue: {str(e)}", exc_info=True)
            raise

    def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """
        Retrieve a document from the catalogue by its MongoDB document ID.
        """
        try:
            collection = self._vector_store.col
            results = collection.query(
                expr=f'document_id == "{document_id}"',
                output_fields=["*"],
            )

            if not results:
                logger.warning(f"Document {document_id} not found in catalogue")
                return None

            result = results[0]
            text = result.get("bm25_text", "")
            metadata = {k: v for k, v in result.items()
                       if k not in ["dense", "sparse", "bm25_text", "pk"]}
            metadata["pk"] = str(result.get("pk", ""))

            return Document(page_content=text, metadata=metadata)

        except Exception as e:
            logger.error(f"Error retrieving document {document_id} from catalogue: {str(e)}", exc_info=True)
            return None

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the catalogue by its MongoDB document ID.
        """
        try:
            collection = self._vector_store.col
            collection.delete(expr=f'document_id == "{document_id}"')
            logger.info(f"Deleted document {document_id} from catalogue")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {document_id} from catalogue: {str(e)}", exc_info=True)
            return False
