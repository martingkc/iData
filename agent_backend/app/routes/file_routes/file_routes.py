from pathlib import Path
from typing import Iterable

from flask import jsonify, request

from ...config.config import FILE_DB_NAME, UNSTRUCTURED_COLLECTION
from ...db import mongo_db_connector
from . import file_bp
from bson import ObjectId
from flask import send_file
from io import BytesIO
from ...services.vector_db.milvus_connector import MilvusConnector
from ...config.config import FILE_DB_NAME, UNSTRUCTURED_COLLECTION
from ...utils.logger import get_logger
from ...routes.auth_routes.auth_extensions import token_auth

_milvus_connector = None

def get_milvus_connector():
    global _milvus_connector
    if _milvus_connector is None:
        _milvus_connector = MilvusConnector(collection_name="document_chunks")
    return _milvus_connector

logger = get_logger(__name__)

def get_path_dict(paths: list[str | Path]) -> dict:
    """
    Builds a tree like structure out of a list of paths
    Extracted from SO - https://stackoverflow.com/questions/58916584/convert-list-of-paths-to-dictionary-in-python   
    """
    def _recurse(dic: dict, chain: tuple[str, ...] | list[str]):
        if len(chain) == 0:
            return
        if len(chain) == 1:
            # Only set to None if not already a dict (directory)
            if chain[0] not in dic or dic[chain[0]] is None:
                dic[chain[0]] = None
            return
        key, *new_chain = chain
        if key not in dic or dic[key] is None:
            # Convert None (file marker) to dict if we need to add children
            dic[key] = {}
        _recurse(dic[key], new_chain)
        return

    new_path_dict = {}
    for path in paths:
        _recurse(new_path_dict, Path(path).parts)
    return new_path_dict


@file_bp.get("/available_files")
@token_auth.login_required
def list_files_tree():
	"""Return a nested map of all files by their `local_path` in MongoDB."""

	collection = mongo_db_connector.get_collection(FILE_DB_NAME, UNSTRUCTURED_COLLECTION)
	cursor = collection.find({"parsed": {"$ne": None, "$ne": ""}}, {"local_path": 1})
	paths = [doc.get("local_path") for doc in cursor if doc.get("local_path")]
	tree = get_path_dict(paths)
	return jsonify({"files": tree})






@file_bp.route('/documents', methods=['GET'])
@token_auth.login_required
def get_documents():
    """Get all documents from MongoDB."""
    try:
        connector = mongo_db_connector
        collection = connector.get_collection(FILE_DB_NAME, UNSTRUCTURED_COLLECTION)
        documents = list(collection.find({}, {
            "_id": 1,
            "local_path": 1,
            "remote_path": 1,
            "context": 1,
            "created": 1,
            "parsed": 1,
            "updated": 1,
            "chunks_count": 1,
            "image_ids": 1
        }))
        
        for doc in documents:
            doc["_id"] = str(doc["_id"])
        
        logger.info(f"Retrieved {len(documents)} documents")
        return jsonify({
            "count": len(documents),
            "documents": documents
        }), 200
    except Exception as e:
        logger.error(f"Error fetching documents: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500



@file_bp.route('/documents/<doc_id>', methods=['GET'])
@token_auth.login_required
def get_document_status(doc_id):
    """Get status and details of a specific document."""
    try:
        connector = mongo_db_connector
        collection = connector.get_collection(FILE_DB_NAME, UNSTRUCTURED_COLLECTION)
        
        document = collection.find_one({"_id": ObjectId(doc_id)})
        
        if not document:
            return jsonify({"error": "Document not found"}), 404
        
        # Convert ObjectId to string
        document["_id"] = str(document["_id"])
        
        # Prepare response
        status = "parsed" if document.get("parsed") else "unparsed"
        
        response = {
            "status": status,
            "document": {
                "_id": document["_id"],
                "local_path": document.get("local_path"),
                "remote_path": document.get("remote_path"),
                "created": document.get("created"),
                "updated": document.get("updated", False),
                "chunks_count": document.get("chunks_count"),
                "context": document.get("context"),
                "milvus_ids": document.get("milvus_ids"),
                "vector_db_error": document.get("vector_db_error"),
                "parsed": document.get("parsed")
            }
        }
        
        logger.info(f"Retrieved document {doc_id} with status: {status}")
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error fetching document status: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@file_bp.route('/documents/search/<query>', methods=['GET'])
@token_auth.login_required
def search_docs(query):
    """Search for chunks matching the query."""
    try:
        connector = MilvusConnector(collection_name="document_chunks")
        # Use search without rerank to avoid FlashRank initialization issues
        results = connector.search(query, k=10, rerank=False)
        
        chunks = []
        for doc in results:
            metadata = doc.metadata or {}
            raw_text = metadata.get("original_text", "")
            chunks.append({
                "chunk_id": str(metadata.get("pk", "")),
                "document_id": metadata.get("document_id", ""),
                "local_path": metadata.get("local_path", ""),
                "content": metadata.get("original_text", "")[:500] + "..." if len(metadata.get("original_text", "")) > 500 else metadata.get("original_text", ""),
                "raw_text": raw_text[:500] + "..." if len(raw_text) > 500 else raw_text,
                "chunk_index": metadata.get("chunk_index", 0),
                "pages": metadata.get("pages", []),
            })
        
        return jsonify({
            "query": query,
            "results": chunks,
            "count": len(chunks)
        }), 200
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@file_bp.route('/api/images/<image_id>', methods=['GET'])
@token_auth.login_required
def get_image(image_id):
    """Serve image by ID from MongoDB assets."""
    try:
        connector = mongo_db_connector
        collection = connector.get_collection(FILE_DB_NAME, UNSTRUCTURED_COLLECTION)
        
        # Find document containing this asset
        doc = collection.find_one(
            {"assets._id": image_id},
            {"assets.$": 1}
        )
        if not doc or 'assets' not in doc:
            return jsonify({"error": "Image not found"}), 404
        asset = doc['assets'][0]
        img_bytes = asset['data']
        
        return send_file(
            BytesIO(img_bytes),
            mimetype=asset.get('mime_type', 'image/png')
        )
    except Exception as e:
        logger.error(f"Error fetching image {image_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@file_bp.route('/documents/reset', methods=['POST'])
@token_auth.login_required
def reset_documents():
    """Reset all documents to unparsed state for testing."""
    try:
        connector = mongo_db_connector
        collection = connector.get_collection(FILE_DB_NAME, UNSTRUCTURED_COLLECTION)
        
        collection.update_many(
            {},
            {
                "$unset": {
                    "parsed_markdown": "",
                    "image_ids": "",
                    "description": "",
                    "milvus_ids": "",
                    "chunks_count": "",
                    "vector_db_error": ""
                }
            }
        )
        
        result = collection.update_many(
            {},
            {"$set": {"updated": True}}
        )
        
        logger.info(f"Reset {result.modified_count} documents to unparsed state")
        return jsonify({
            "message": "All documents reset to unparsed state",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        logger.error(f"Error resetting documents: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@file_bp.route('/documents/<document_id>/<chunk_id>', methods=['GET'])
@token_auth.login_required
def get_chunk_by_id(document_id: str, chunk_id: str):
    """
    Retrieve a specific chunk by its document ID and chunk ID.
    
    The chunk_id is the Milvus primary key (pk) of the chunk.
    Returns the chunk content and metadata.
    """
    try:
        milvus = get_milvus_connector()
        chunk = milvus.get_chunk_by_id(chunk_id)
        
        if chunk is None:
            return jsonify({"error": f"Chunk {chunk_id} not found"}), 404
        
        # Verify the chunk belongs to the specified document
        chunk_doc_id = chunk.metadata.get("document_id", "")
        if chunk_doc_id and chunk_doc_id != document_id:
            return jsonify({
                "error": f"Chunk {chunk_id} does not belong to document {document_id}"
            }), 404
        
        return jsonify({
            "chunk_id": chunk_id,
            "document_id": document_id,
            "content": chunk.metadata.get("original_text", ""),
        })
        
    except Exception as e:
        logger.error(f"Error fetching chunk {chunk_id}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@file_bp.route('/chunks/<chunk_id>', methods=['GET'])
@token_auth.login_required
def get_chunk(chunk_id: str):
    """
    Retrieve a specific chunk by its chunk ID only.
    
    The chunk_id is the Milvus primary key (pk) of the chunk.
    Returns the chunk content and metadata.
    """
    try:
        milvus = get_milvus_connector()
        chunk = milvus.get_chunk_by_id(chunk_id)
        
        if chunk is None:
            return jsonify({"error": f"Chunk {chunk_id} not found"}), 404
        
        return jsonify({
            "chunk_id": chunk_id,
            "document_id": chunk.metadata.get("document_id", ""),
            "content": chunk.metadata.get("original_text", ""),
            
        })
        
    except Exception as e:
        logger.error(f"Error fetching chunk {chunk_id}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@file_bp.route('/chunks/batch', methods=['POST'])
@token_auth.login_required
def get_chunks_batch():
    """
    Retrieve multiple chunks by their IDs.
    
    Request body: {"chunk_ids": ["id1", "id2", ...]}
    Returns list of chunks with their content and metadata.
    """
    try:
        data = request.get_json()
        chunk_ids = data.get("chunk_ids", [])
        
        if not chunk_ids:
            return jsonify({"error": "No chunk_ids provided"}), 400
        
        milvus = get_milvus_connector()
        chunks = milvus.get_chunks_by_ids(chunk_ids)
        
        result = []
        for chunk in chunks:
            result.append({
                "chunk_id": chunk.metadata.get("pk", ""),
                "document_id": chunk.metadata.get("document_id", ""),
                "content": chunk.metadata.get("original_text", ""),
                "metadata": chunk.metadata,
            })
        
        return jsonify({"chunks": result})
        
    except Exception as e:
        logger.error(f"Error fetching chunks batch: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
