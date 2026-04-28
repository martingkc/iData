import os
import time
import atexit
import json
import logging
from threading import Timer
from threading import Lock
from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    DirCreatedEvent,
    DirModifiedEvent,
    DirDeletedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
    FileMovedEvent,
)
from document_collector.globals import (
    LOCAL_DOCUMENTS_FOLDER_PATH,
    MONGODB_CONNECTION_STRING,
    MONGODB_NAME,
    MONGODB_COLLECTION_NAME,
    WATCHDOG_GLOBAL_OBSERVER_TIMEOUT_SECONDS,
)
import pymongo
from document_collector.exception_handlers import MongoSafeContext
from watchdog.observers.polling import PollingObserver

logger = logging.getLogger(__name__)


def check_is_file_decorator(func):
    """We only want to process files, not directories"""

    def wrapper(self, event):
        if not event.is_directory:
            return func(self, event)
        else:
            logger.info("Ignored directory event: %s", event.src_path)

    return wrapper


class Handler(FileSystemEventHandler):
    def __init__(
        self,
        mongo_db_client=None,
        mongo_db_name=MONGODB_NAME,
        mongo_collection_name=MONGODB_COLLECTION_NAME,
    ):
        super().__init__()
        self.mongo_db_client = mongo_db_client or pymongo.MongoClient(
            MONGODB_CONNECTION_STRING
        )
        self.mongo_db_name = mongo_db_name
        self.mongo_collection_name = mongo_collection_name
        # When the handler is initialized, check the whole folder and add the files to MongoDB, in case there are already files in the folder before the watchdog starts.
        self._check_the_whole_folder()

    def _check_the_whole_folder(self, folder_path=LOCAL_DOCUMENTS_FOLDER_PATH):
        # This function is to check the whole folder and add the files to MongoDB when the server starts, in case there are already files in the folder before the watchdog starts.
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                with MongoSafeContext(logger=logger) as mongo_context:
                    self.mongo_db_client[self.mongo_db_name][
                        self.mongo_collection_name
                    ].update_one(
                        {"local_path": file_path},
                        {"$set": {"updated": False}},
                        upsert=True,
                    )
                    logger.info("File information added to MongoDB for: %s", file_path)
            # recursively check subdirectories
            for dir_ in dirs:
                dir_path = os.path.join(root, dir_)
                self._check_the_whole_folder(dir_path)

    @check_is_file_decorator
    def on_modified(self, event):
        logger.info("File modified: %s", event.src_path)
        logger.info("details: %s", event)
        # Update the file information in MongoDB
        # the path is the same but the content is changed, set updated to true
        with MongoSafeContext(logger=logger) as mongo_context:
            self.mongo_db_client[self.mongo_db_name][
                self.mongo_collection_name
            ].update_one({"local_path": event.src_path}, {"$set": {"updated": True}})
            logger.info("File information updated in MongoDB for: %s", event.src_path)
        return

    @check_is_file_decorator
    def on_created(self, event):
        # add to mongodb
        logger.info("File created: %s", event.src_path)
        logger.info("details: %s", event)
        # Add file information to MongoDB
        # add local_path and updated false
        with MongoSafeContext(logger=logger) as mongo_context:
            self.mongo_db_client[self.mongo_db_name][
                self.mongo_collection_name
            ].insert_one(
                {
                    "local_path": event.src_path,
                    "updated": False,
                }
            )
            logger.info("File information added to MongoDB for: %s", event.src_path)
        return

    @check_is_file_decorator
    def on_deleted(self, event):
        # make null or delete the path in mongodb
        logger.info("File deleted: %s", event.src_path)
        logger.info("details: %s", event)
        # Remove file information from MongoDB
        with MongoSafeContext(logger=logger) as mongo_context:
            self.mongo_db_client[self.mongo_db_name][
                self.mongo_collection_name
            ].delete_one({"local_path": event.src_path})
            logger.info("File information removed from MongoDB for: %s", event.src_path)
        return

    @check_is_file_decorator
    def on_moved(self, event):
        # update the path in mongodb, parse remains the same
        logger.info("File moved from %s to %s", event.src_path, event.dest_path)
        logger.info("details: %s", event)
        # Update the file path in MongoDB
        with MongoSafeContext(logger=logger) as mongo_context:
            self.mongo_db_client[self.mongo_db_name][
                self.mongo_collection_name
            ].update_one(
                {"local_path": event.src_path},
                {"$set": {"local_path": event.dest_path}},
            )
            logger.info(
                "File path updated in MongoDB from %s to %s",
                event.src_path,
                event.dest_path,
            )
        return


observer = PollingObserver(timeout=WATCHDOG_GLOBAL_OBSERVER_TIMEOUT_SECONDS)


def stop_observer():
    global observer
    observer.stop()
    observer.join()


def start_folder_watchdog():
    global observer
    event_handler = Handler()
    logger.info("Starting folder watchdog for path: %s", LOCAL_DOCUMENTS_FOLDER_PATH)
    observer.schedule(event_handler, LOCAL_DOCUMENTS_FOLDER_PATH, recursive=True)
    observer.start()
    atexit.register(stop_observer)  # ensure the observer stops when the program exits
    observer.join()
