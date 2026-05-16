import os
from flashrank import Ranker
from typing import Optional, Dict, Any, List, Tuple, Union
from langchain_community.document_compressors import FlashrankRerank
from langchain_milvus import BM25BuiltInFunction, Milvus
from langchain_core.documents import Document
from .lm_studio_embeddings import LMStudioEmbeddings
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from pymilvus import connections, Collection

from ...utils.logger import get_logger
from ...config.config import MILVUS_HOST, MILVUS_PORT

logger = get_logger(__name__)


class MilvusConnector:
    """
    Milvus vector database connector.
    Manages connection to Milvus vector database with automatic initialization
    and error handling. Supports both local and remote connections.

    Current retreival process:
    if rerank has been set it uses FlashRank to rerank the query results using a Bert Model
    It's highly CPU efficient, so it should be able to run on a VCPU instance too, check more on langchain.
    """

    def __init__(
        self,
        embeddings=LMStudioEmbeddings(),
        uri: Optional[str] = None,
        collection_name: str = "document_chunks",
        builtin_function: BM25BuiltInFunction = BM25BuiltInFunction(
            input_field_names="bm25_text",
            output_field_names="sparse",
        ),
        index_type: str = "FLAT",
        metric_type: str = "COSINE",
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        self._embeddings = embeddings
        self._collection_name = collection_name
        self._builtin_function = builtin_function

        try:
            connection_args = self._construct_connection_args(uri, host, port)
            print(f"Connecting to Milvus with args: {connection_args}")

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
                builtin_function=builtin_function,
                vector_field=["dense", "sparse"],
                text_field="bm25_text",
                enable_dynamic_field=True,
            )
            self._compressor = FlashrankRerank()
            self._compression_retreiver = ContextualCompressionRetriever(
                base_compressor=self._compressor,
                base_retriever=self._vector_store.as_retriever(
                    search_kwargs={
                        "k": 10,
                        "ranker_type": "weighted",
                        "ranker_params": {"weights": [0.7, 0.3]},
                    }
                ),
            )

            logger.info(
                f"Milvus connector initialized with collection: {collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Milvus: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def _construct_connection_args(
        uri: Optional[str],
        host: Optional[str],
        port: Optional[int],
    ) -> Dict[str, Any]:
        """
        This is purely optional
        """
        connection_args: Dict[str, Any] = {}

        if uri:
            connection_args["uri"] = uri
            logger.debug(f"Using Milvus URI: {uri}")
            return connection_args
        host = MILVUS_HOST
        port = MILVUS_PORT
        if host and port:
            connection_args["host"] = host
            connection_args["port"] = port
            connection_args["uri"] = f"http://{host}:{port}"
            logger.debug(f"Using Milvus connection: {host}:{port}")
            return connection_args

        # env_uri = os.getenv("MILVUS_URI")
        """if env_uri:
            connection_args["uri"] = env_uri
            logger.debug(f"Using Milvus URI from env: {env_uri}")
            return connection_args
        """
        env_host = MILVUS_HOST
        env_port = MILVUS_PORT
        print(f"ENV HOST PORT: {env_host} {env_port}")
        if env_host and env_port:
            connection_args["host"] = env_host
            connection_args["port"] = int(env_port)
            logger.debug(f"Using Milvus connection from env: {env_host}:{env_port}")
            return connection_args

        default_uri = os.getenv("MILVUS_DB_PATH", "./milvus_data.db")
        connection_args["uri"] = default_uri
        logger.debug(f"Using default local Milvus database: {default_uri}")
        return connection_args

    def _ensure_bm25_text(self, doc: Document) -> None:
        """
        Ensure doc.metadata["bm25_text"] exists.

        Option B: BM25 reads this field.
        - Preferred: upstream chunking sets it (context + chunk text + tags).
        - Fallback here: use context (if any) + page_content.
        """
        if doc.metadata is None:
            doc.metadata = {}

        if "bm25_text" in doc.metadata and doc.metadata["bm25_text"]:
            return

        context = doc.metadata.get("context", "") or ""
        text = doc.page_content or ""

        parts = []
        if context:
            parts.append(str(context))
        if text:
            parts.append(str(text))

        bm25_text = " ".join(p.strip() for p in parts if p and p.strip())
        doc.metadata["bm25_text"] = bm25_text

    def add_documents(self, documents: List[Document], ids=None):
        """Add documents to Milvus."""
        try:
            if not documents:
                logger.warning("No documents to add to Milvus")
                return []

            # Ensure all documents have required fields
            for doc in documents:
                if not hasattr(doc, "metadata") or doc.metadata is None:
                    doc.metadata = {}

                # Ensure 'kind' field exists
                if "kind" not in doc.metadata:
                    doc.metadata["kind"] = "chunk"

                # Ensure bm25_text exists for Option B
                self._ensure_bm25_text(doc)

            result_ids = self._vector_store.add_documents(documents, ids=ids)
            logger.info(f"Added {len(result_ids)} documents to Milvus")
            return result_ids
        except Exception as e:
            logger.error(f"Error adding documents to Milvus: {str(e)}", exc_info=True)
            raise

    def search(
        self,
        query: str,
        k: int,
        weights: Tuple[float, float] = (0.7, 0.3),
        expr: Optional[str] = None,
        rerank: Optional[bool] = None
    ):
        """
        Hybrid search (dense + BM25) with weighted rerank.

        Parameters
        ----------
        query : str
            User query.
        k : int
            Number of results to return.
        weights : (dense_weight, sparse_weight)
            How much to trust embeddings vs BM25.
            (0.7, 0.3) = mostly semantic, some lexical.
        expr : str, optional
            Milvus filter expression (e.g., 'local_path in ["a.pdf", "b.pdf"]').
        """
        if rerank is None and k > 5:
            rerank = True  # Auto-enable reranking for larger k
        elif rerank is None:
            rerank = False  # No reranking for small k by default
            
        try:
            search_kwargs = {
                "k": k if not rerank  else k * 2,  # fetch more for reranker
                "ranker_type": "weighted",
                "ranker_params": {"weights": list(weights)},
            }
            if expr:
                search_kwargs["expr"] = expr

            if not rerank:
                docs = self._vector_store.similarity_search(query, **search_kwargs)
            else:
                # Build a fresh retriever with the filter applied
                retriever = self._vector_store.as_retriever(search_kwargs=search_kwargs)
                compression_retriever = ContextualCompressionRetriever(
                    base_compressor=self._compressor,
                    base_retriever=retriever,
                )
                docs = compression_retriever.invoke(query)[:k]
            
            # Fetch bm25_text for all returned documents using their pks
            # This ensures we get the full text including tables
            pks = [doc.metadata.get("pk") for doc in docs if doc.metadata and doc.metadata.get("pk")]
            if pks:
                try:
                    collection = self._vector_store.col
                    pk_list = ", ".join(str(pk) for pk in pks)
                    results = collection.query(
                        expr=f"pk in [{pk_list}]",
                        output_fields=["pk", "bm25_text"],
                    )
                    # Create a mapping of pk -> bm25_text
                    pk_to_text = {r["pk"]: r.get("bm25_text", "") for r in results}
                    
                    # Update documents with bm25_text in metadata
                    for doc in docs:
                        pk = doc.metadata.get("pk")
                        if pk and pk in pk_to_text:
                            doc.metadata["bm25_text"] = pk_to_text[pk]
                except Exception as e:
                    logger.warning(f"Failed to fetch bm25_text for documents: {e}")
            
            # Ensure pk is in metadata for each document
            for doc in docs:
                if doc.metadata and "pk" not in doc.metadata:
                    logger.warning(f"Document missing pk in metadata: {doc.metadata.keys()}")
            
            return docs
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}", exc_info=True)
            raise

    def search_with_score(
        self,
        query: str,
        k: int = 5,
        weights: Tuple[float, float] = (0.7, 0.3),
        expr: Optional[str] = None,
        rerank: bool = True,
    ):
        """
        Same as `search` but returns (Document, score).

        This still uses hybrid weighted ranking with dense + BM25 with the weights set on weights.
        """
        try:
            if not rerank:
                return self._vector_store.similarity_search_with_score(
                    query,
                    k=k,
                    ranker_type="weighted",
                    ranker_params={"weights": list(weights)},
                    expr=expr,
                )
            else:

                return self._compression_retreiver.invoke(query)[:k]
        except Exception as e:
            logger.error(
                f"Error searching documents with score: {str(e)}", exc_info=True
            )
            raise

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Document]:
        """
        Retrieve a single chunk by its Milvus primary key (pk).
        
        Parameters
        ----------
        chunk_id : str
            The Milvus primary key of the chunk to retrieve.
            
        Returns
        -------
        Document or None
            The chunk as a LangChain Document, or None if not found.
        """
        try:
            # Use the underlying Milvus collection to query by pk
            collection = self._vector_store.col
            
            # Query by primary key - pk is Int64, so don't use quotes
            results = collection.query(
                expr=f'pk == {chunk_id}',
                output_fields=["*"],  # Get all fields
            )
            
            if not results:
                logger.warning(f"Chunk with id {chunk_id} not found")
                return None
            
            result = results[0]
            
            # Extract text content and metadata
            text = result.get("text", result.get("bm25_text", ""))
            
            # Build metadata from all other fields
            metadata = {k: v for k, v in result.items() 
                       if k not in ["dense", "sparse", "text", "pk"]}
            metadata["pk"] = str(result.get("pk", chunk_id))  # Convert to string for consistency
            
            return Document(page_content=text, metadata=metadata)
            
        except Exception as e:
            logger.error(f"Error retrieving chunk by id {chunk_id}: {str(e)}", exc_info=True)
            return None

    def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[Document]:
        """
        Retrieve multiple chunks by their Milvus primary keys.
        
        Parameters
        ----------
        chunk_ids : List[str]
            List of Milvus primary keys to retrieve.
            
        Returns
        -------
        List[Document]
            List of chunks as LangChain Documents. Missing chunks are omitted.
        """
        try:
            if not chunk_ids:
                return []
                
            collection = self._vector_store.col
            
            # Build expression for multiple IDs - pk is Int64, so don't use quotes
            ids_str = ', '.join(chunk_ids)
            expr = f'pk in [{ids_str}]'
            
            results = collection.query(
                expr=expr,
                output_fields=["*"],
            )
            
            documents = []
            for result in results:
                text = result.get("text", result.get("bm25_text", ""))
                metadata = {k: v for k, v in result.items() 
                           if k not in ["dense", "sparse", "text", "pk"]}
                metadata["pk"] = str(result.get("pk"))  # Convert to string for consistency
                documents.append(Document(page_content=text, metadata=metadata))
            
            logger.info(f"Retrieved {len(documents)} chunks out of {len(chunk_ids)} requested")
            return documents
            
        except Exception as e:
            logger.error(f"Error retrieving chunks by ids: {str(e)}", exc_info=True)
            return []
