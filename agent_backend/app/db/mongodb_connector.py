import pymongo
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from ..config.config import MONGODB_ADDRESS, MONGODB_PORT, MONGODB_USERNAME, MONGODB_PASSWORD
from ..utils.logger import get_logger


logger = get_logger(__name__)


class MongoDBConnector:
    """
    MongoDB connector with connection validation and error handling.
    """

    def __init__(self):
        self._client = None
        self._initialize_connection()

    def _initialize_connection(self):
        """Initialize MongoDB connection"""
        try:
            self._client = pymongo.MongoClient(
                MONGODB_ADDRESS,
                MONGODB_PORT,
                username=MONGODB_USERNAME,
                password=MONGODB_PASSWORD,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
            )
            logger.info(
                f"MongoDB connected successfully to {MONGODB_ADDRESS}:{MONGODB_PORT}"
            )
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(
                f"Failed to connect to MongoDB at {MONGODB_ADDRESS}:{MONGODB_PORT}. Error: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {str(e)}")
            raise

    @property
    def client(self):
        """Get the MongoDB client."""
        if self._client is None:
            self._initialize_connection()
        return self._client

    def get_database(self, db_name: str):
        """
        Get a database from the MongoDB client.
        """
        try:
            return self.client[db_name]
        except Exception as e:
            logger.error(f"Error accessing database '{db_name}': {str(e)}")
            raise

    def get_collection(self, db_name: str, collection_name: str):
        """
        Get a collection from a specific database.
        """
        try:
            db = self.get_database(db_name)
            return db[collection_name]
        except Exception as e:
            logger.error(
                f"Error accessing collection '{collection_name}' in database '{db_name}': {str(e)}"
            )
            raise

    def close(self):
        """
        Close the MongoDB connection.
        """
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed")