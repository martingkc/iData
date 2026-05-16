import os
from dotenv import load_dotenv

load_dotenv()
"""
TODO: before deployment change this to the FLASK config file. 
"""
CONTEXT_SUMMARIZATION_MODEL = os.getenv("CONTEXT_SUMMARIZATION_MODEL", "gemma-4")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1")
MONGODB_ADDRESS = os.getenv("MONGODB_ADDRESS")
MONGODB_PORT = int(os.getenv("MONGODB_PORT"))
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "berkdorukmartin")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "12345dorukmartin")
FILE_DB_NAME = os.getenv("MONGODB_NAME", "FILE_BUCKET")
UNSTRUCTURED_COLLECTION = os.getenv("MONGODB_COLLECTION_NAME", "UNSTRUCTURED_COLLECTION")
MILVUS_HOST =  os.getenv("MILVUS_HOST")
MILVUS_PORT =  int(os.getenv("MILVUS_PORT"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "*")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
