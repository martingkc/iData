import os
from urllib.parse import (
    quote_plus,
)  # For safely encoding database credentials in the connection URI
from dotenv import load_dotenv

load_dotenv()
"""
TODO: before deployment change this to the FLASK config file. 
"""
CONTEXT_SUMMARIZATION_MODEL = os.getenv("CONTEXT_SUMMARIZATION_MODEL", "gpt-4.1-mini")
MONGODB_ADDRESS = os.getenv("MONGODB_ADDRESS")
MONGODB_PORT = int(os.getenv("MONGODB_PORT"))
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "")
FILE_DB_NAME = os.getenv("MONGODB_NAME", "FILE_BUCKET")
UNSTRUCTURED_COLLECTION = os.getenv(
    "MONGODB_COLLECTION_NAME", "UNSTRUCTURED_COLLECTION"
)
MILVUS_HOST = os.getenv("MILVUS_HOST")
MILVUS_PORT = int(os.getenv("MILVUS_PORT"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "*")
# Default to the bundled users.db SQLite DB under app/db. Override via SQL_AGENTDB_URI.
SQL_AGENTDB_URI = os.getenv("SQL_AGENTDB_URI", "sqlite:////app/app/db/users.db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
JWT_SECRET = os.getenv("JWT_SECRET")
POSTGRES_USERDB_URL = os.getenv(
    "POSTGRES_USERDB_URL",
    f"postgresql+psycopg2://{quote_plus(POSTGRES_USER)}:{quote_plus(POSTGRES_PASSWORD)}@{POSTGRES_HOST}:5432/{quote_plus(POSTGRES_DB)}",
)

POSTGRES_CHECKPOINT_URL = os.getenv(
    "POSTGRES_CHECKPOINT_URL",
    f"dbname={quote_plus(POSTGRES_DB)} user={quote_plus(POSTGRES_USER)} password={quote_plus(POSTGRES_PASSWORD)} host={POSTGRES_HOST} port=5432",
)   
