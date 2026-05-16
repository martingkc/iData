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

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        embeddings=None,
        uri: Optional[str] = None,
        collection_name: str = "document_catalogue",
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        if DocumentCatalogueConnector._initialized:
            return
            
        if embeddings is None:
            embeddings = LMStudioEmbeddings()
            
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
            )
            self._compressor = FlashrankRerank()

            logger.info(
                f"DocumentCatalogueConnector initialized with collection: {collection_name}"
            )
            DocumentCatalogueConnector._initialized = True
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

    