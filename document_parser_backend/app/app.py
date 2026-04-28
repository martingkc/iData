import os
from datetime import datetime
import time
from flask import Flask, jsonify
from flask_cors import CORS
from .db.mongodb_connector import MongoDBConnector
from .config.config import FILE_DB_NAME, UNSTRUCTURED_COLLECTION
from .threads.file_parser_thread import start_file_parser_thread
from .routes import  documents_bp
from .utils.logger import get_logger

logger = get_logger(__name__)


def create_app():
    """
    Create and configure the Flask application.

    TODO: Remove `_initialize_sample_documents` from this function. 
    """
    app = Flask(__name__)
    
    # Enable CORS for all routes
    CORS(app, resources={r"/*": {"origins": "*"}})

    app.register_blueprint(documents_bp)
    
    try:
        MongoDBConnector()
        #_initialize_sample_documents()
        start_file_parser_thread(app)
        logger.info("MongoDB connector initialized")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {str(e)}")
        raise
  
    
    return app


def _initialize_sample_documents():
    """
    Create 4 sample PDF documents in MongoDB for testing.
    TODO: Remove this function when test env is set correctly 
    """
    try:
        # Get connector
        connector = MongoDBConnector()
        # Get collection cursor 
        collection = connector.get_collection(FILE_DB_NAME, UNSTRUCTURED_COLLECTION)      
        # Delete all entries 
        collection.delete_many({})
        

        # Define your docs - this is the structure I had in mind LMK if you want to change it. 
        # Just replace `local_path` with your own path. 
        sample_documents = [
    
       {
                    "local_path": "/app/Backend/Backend/example_folders/champ.pdf",
                    "remote_path": "s3://bucket/sample_document_3.pdf",
                    "created": time.time(),
                    "updated": False,
                    "image_ids": []
                } ,{
                    "local_path": "/app/Backend/Backend/example_folders/ass.pdf",
                    "remote_path": "s3://bucket/sample_document_2.pdf",
                    "created": time.time(),
                    "updated": False,
                    "image_ids": []
                },
                {
                    "local_path": "/app/Backend/Backend/example_folders/manch.pdf",
                    "remote_path": "s3://bucket/sample_document_3.pdf",
                    "created": time.time(),
                    "updated": False,
                    "image_ids": []
                },
        {
                    "local_path": "/app/Backend/Backend/example_folders/RASDdone.pdf",
                    "remote_path": "s3://bucket/sample_document_3.pdf",
                    "created": time.time(),
                    "updated": False,
                    "image_ids": []
        }  
    
        ]

 
    
        # Insert your sample docs 
        result = collection.insert_many(sample_documents)
        logger.info(f"Created {len(result.inserted_ids)} sample documents")

    except Exception as e:
        logger.error(f"Error initializing sample documents: {str(e)}")
        raise

