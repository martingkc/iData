import tomllib
from urllib.parse import quote_plus
import os
import logging
from logger.setup_logging import setup_logging

# get folder path containing all the configuration files
CONFIGS_FOLDER_PATH = os.environ.get("CONFIGS_FOLDER_PATH", "configs")
# get different relative paths under configs folder
CONFIG_FILE_RELATIVE_PATH = os.environ.get("CONFIG_FILE_PATH", "config.toml")
LOGGER_CONFIG_FILE_RELATIVE_PATH = os.environ.get(
    "LOGGER_CONFIG_FILE_RELATIVE_PATH", "logger_config.json"
)
# construct full path for different config files
CONFIG_FILE_PATH = os.path.join(CONFIGS_FOLDER_PATH, CONFIG_FILE_RELATIVE_PATH)
if not os.path.exists(CONFIG_FILE_PATH):
    raise FileNotFoundError(f"Configuration file not found at {CONFIG_FILE_PATH}")
with open(CONFIG_FILE_PATH, "rb") as config_file:
    config_data = tomllib.load(config_file)
# set global variables from config file or environment variables
NAS_DOCUMENTS_FOLDER_PATH = config_data.get("folder_paths", {}).get(
    "nas_documents_path"
)
LOCAL_DOCUMENTS_FOLDER_PATH = config_data.get("folder_paths", {}).get(
    "local_documents_folder"
)
CLIENT_SIDE_CONFIGURATION_API_PORT = config_data.get(
    "client_side_configuration", {}
).get("api_port", 13000)
# construct full path for logger config file
LOGGER_CONFIG_FILE_PATH = os.path.join(
    CONFIGS_FOLDER_PATH, LOGGER_CONFIG_FILE_RELATIVE_PATH
)
# setup logging configuration
setup_logging(LOGGER_CONFIG_FILE_PATH)
logger = logging.getLogger(__name__)
# set default values for global variables
LOCAL_DOCUMENTS_FOLDER_PATH = os.environ.get(
    "LOCAL_DOCUMENTS_FOLDER_PATH", "local-documents"
)
WATCHDOG_GLOBAL_OBSERVER_TIMEOUT_SECONDS = int(
    os.environ.get("WATCHDOG_GLOBAL_OBSERVER_TIMEOUT_SECONDS", "1")
)
# Construct MongoDB connection string
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "berkdorukmartin")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "12345dorukmartin")
MONGODB_PORT = os.getenv("MONGODB_PORT", "27017")
MONGODB_ADDRESS = os.getenv("MONGODB_ADDRESS", "localhost")
MONGODB_CONNECTION_STRING = (
    f"mongodb://{quote_plus(MONGODB_USERNAME)}:{quote_plus(MONGODB_PASSWORD)}@"
    f"{MONGODB_ADDRESS}:{MONGODB_PORT}"
)  # Make sure to quote special characters in username/password

MONGODB_COLLECTION_NAME = os.getenv(
    "MONGODB_COLLECTION_NAME", "UNSTRUCTURED_COLLECTION"
)
MONGODB_NAME = os.getenv("MONGODB_NAME", "FILE_BUCKET")
