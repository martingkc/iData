import os
from ..config.config import POSTGRES_USERDB_URL
from sqlalchemy import create_engine
from .mongodb_connector import MongoDBConnector
from sqlalchemy.orm import declarative_base, sessionmaker

mongo_db_connector = MongoDBConnector()

engine = create_engine(POSTGRES_USERDB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def init_db():
    Base.metadata.create_all(bind=engine)