from flask import Blueprint, jsonify, request
from bson import ObjectId
from flask import send_file
from io import BytesIO
from ..services.vector_db.milvus_connector import MilvusConnector
from ..db.mongodb_connector import MongoDBConnector
from ..config.config import FILE_DB_NAME, UNSTRUCTURED_COLLECTION
from ..utils.logger import get_logger

logger = get_logger(__name__)

documents_bp = Blueprint('documents', __name__)
