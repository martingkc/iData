from ...db import mongo_db_connector
from ...config.config import FILE_DB_NAME, UNSTRUCTURED_COLLECTION
from ...utils.logger import get_logger


class FileFetcher:
    """
    Service for fetching files from MongoDB.

    KISACA: Tek yaptigi sey mongo collectionunu yoklamak ve yeni dokuman varsa paslamak pek de bi sikimi yapmiyor. 
    """

    def __init__(self, db_name: str = FILE_DB_NAME, collection_name: str = UNSTRUCTURED_COLLECTION):
        self.logger = get_logger(__name__)
        try:
            self.collection = mongo_db_connector.get_collection(db_name=db_name, collection_name=collection_name)
            self.logger.info(f"FileFetcher initialized with database {db_name} collection {collection_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize FileFetcher: {str(e)}")
            raise

    def get_file(self, file_id):
        """
        Fetch a single file by ID.
        """
        try:
            return self.collection.find_one({"_id": file_id})
        except Exception as e:
            self.logger.error(f"Error fetching file with ID {file_id}: {str(e)}")
            raise
    
    def get_files_to_parse(self):
        """
        Fetch files that need parsing (unparsed OR recently updated).
        Excludes documents that have previously failed parsing.
        """
        try:
            query = {
                "local_path": {"$exists": True},
                "parse_failed": {"$ne": True},  # Exclude documents that failed parsing
                "$or": [
                    {"parsed": {"$exists": False}},
                    {"updated": True}
                ]
            }
            files = list(self.collection.find(query))
            self.logger.info(f"Found {len(files)} files to parse")
            return files
        except Exception as e:
            self.logger.error(f"Error fetching files to parse: {str(e)}")
            raise

    

