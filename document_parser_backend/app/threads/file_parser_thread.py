import datetime
import time
import threading
import asyncio
import gc


from ..services.file_fetcher.file_fetcher import FileFetcher
from ..services.document_parser.document_parser_service import DocumentParser
from ..services.vector_db.milvus_connector import MilvusConnector
from ..services.vector_db.document_catalogue_connector import DocumentCatalogueConnector
from ..utils.logger import get_logger
from ..services.vector_db.lm_studio_embeddings import LMStudioEmbeddings

logger = get_logger(__name__)


async def file_parser_thread(app, VLM=False):
    """
    Thread that periodically fetches new documents from MongoDB, parses them, and saves to the vector db.

    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    !!!! DO NOT FORGET TO CHANGE THE asyncio.sleep(TIME) and SET UP THE VLM PARAM !!!!
    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    TODO: check if the images get stored correctly it seems excessive saing the image_ids twice both as metadata on Mongo and on Milvus.
    TODO: manage the case where the file is updated. Delete the embeddings/chunks belonging to that doc from the vector db.
    TODO: check step 6 of the pipeline. Evaluate that idea
    """
    try:
        document_parser_service = DocumentParser()
        file_fetcher_service = FileFetcher()
        embeddings = LMStudioEmbeddings()
        milvus_connector_service = MilvusConnector(
            embeddings=embeddings,
            collection_name="document_chunks",
        )
        # Initialize document catalogue connector for document-level metadata
        document_catalogue_service = DocumentCatalogueConnector(
            embeddings=embeddings,
            collection_name="document_catalogue",
        )
        logger.info("Milvus connectors initialized successfully (chunks + catalogue)")
    except Exception as e:
        logger.error(
            f"file_parser_thread: Failed to initialize services: {str(e)}",
            exc_info=True,
        )
        return

    while True:
        try:
            files_to_parse = file_fetcher_service.get_files_to_parse()

            if not files_to_parse:
                logger.info("No files to parse")

            for doc in files_to_parse:
                try:
                    _id = doc["_id"]
                    logger.info(f"Processing document {_id}")

                    # 1 - Parse document to markdown
                    try:
                        parsed_document, parsed_docling = (
                            document_parser_service.parse_to_md(doc)
                        )
                    except Exception as parse_error:
                        logger.error(
                            f"Error parsing document {_id}: {str(parse_error)}",
                            exc_info=True,
                        )
                        # Mark document as failed to prevent infinite retry loops
                        file_fetcher_service.collection.update_one(
                            {"_id": _id},
                            {
                                "$set": {
                                    "parse_error": str(parse_error),
                                    "parse_failed": True,
                                    "parse_failed_at": time.time(),
                                }
                            },
                        )
                        gc.collect()
                        continue

                    logger.info(f"Successfully parsed document {_id}")

                    # 2 - Choose the metadata you want to store in the vector db
                    metadata = {
                        "document_id": str(_id),
                        "context": doc.get("context", ""),
                        "local_path": doc.get("local_path", ""),
                        "remote_path": doc.get("remote_path", ""),
                        "created": str(doc.get("created", "")),
                        "processed": str(time.time()),
                    }
                    # 3 - Chunk the parsed file
                    try:
                        chunks = document_parser_service.hierarchical_chunking(
                            parsed_docling, metadata
                        )
                    except Exception as chunk_error:
                        logger.error(
                            f"Error in hierarchical_chunking for document {_id}: {str(chunk_error)}",
                            exc_info=True,
                        )
                        continue
                    finally:
                        # Clean up parsed_docling to free memory
                        del parsed_docling
                        gc.collect()

                    if not chunks:
                        logger.warning(f"No chunks generated for document {_id}")
                        continue

                    logger.debug(f"Generated {len(chunks)} chunks for document {_id}")

                    try:
                        # 4 - Load the LC Documents on the vector DB
                        milvus_ids = milvus_connector_service.add_documents(chunks)
                        logger.info(
                            f"Successfully saved {len(milvus_ids)} chunks to Milvus for document {_id}"
                        )

                        # 4.5 - Add document to catalogue (document-level metadata with hybrid search)
                        try:
                            catalogue_ids = document_catalogue_service.add_document(
                                document_id=str(_id),
                                context=parsed_document.get("context", ""),
                                local_path=doc.get("local_path", ""),
                                remote_path=doc.get("remote_path", ""),
                                created=str(doc.get("created", "")),
                                parsed=parsed_document.get("parsed", ""),
                                image_ids=parsed_document.get("image_ids", []),
                                table_ids=parsed_document.get("table_ids", []),
                            )
                            logger.info(
                                f"Added document {_id} to catalogue with ids {catalogue_ids}"
                            )
                        except Exception as catalogue_error:
                            logger.error(
                                f"Error adding document {_id} to catalogue: {str(catalogue_error)}",
                                exc_info=True,
                            )
                            # Continue even if catalogue fails - chunks are more important

                        # 5 - Update the entry for the Doc on mongo.
                        file_fetcher_service.collection.update_one(
                            {"_id": _id},
                            {
                                "$set": {
                                    "parsed": parsed_document.get("parsed"),
                                    "image_ids": parsed_document.get("image_ids", []),
                                    "table_ids": parsed_document.get("table_ids", []),
                                    "context": parsed_document.get("context"),
                                    "assets": parsed_document.get("assets", []),
                                    "updated": False,
                                    "milvus_ids": milvus_ids,
                                }
                            },
                        )

                        logger.info(
                            f"Updated document {_id} with {len(milvus_ids)} Milvus reference and parsed MD"
                        )

                        # 6 - ??? Just a thought but maybe we should delete the copy of the doc since we dont need it anymore

                    except Exception as e:
                        logger.error(
                            f"Error adding chunks to Milvus for document {_id}: {str(e)}",
                        )
                        continue
                    finally:
                        # Clean up chunks to free memory
                        del chunks
                        del parsed_document
                        gc.collect()

                except Exception as e:
                    logger.error(
                        f"Error processing document {doc.get('_id', 'unknown')}: {str(e)}",
                    )
                    continue

            # sleep for 1 hour before next check
            await asyncio.sleep(60)
            gc.collect()

        except Exception as e:
            logger.error(f"Error in file_parser_thread: {str(e)}")
            await asyncio.sleep(60)


def start_file_parser_thread(app):
    """Start the file parser thread as a daemon."""
    try:
        t = threading.Thread(
            target=lambda: asyncio.run(file_parser_thread(app)),
            daemon=True,
            name="FileParserThread",
        )
        t.start()
        logger.info("start_file_parser_thread: File parser thread started successfully")
    except Exception as e:
        logger.error(
            f"start_file_parser_thread: Failed to start file parser thread: {str(e)}"
        )
        raise
