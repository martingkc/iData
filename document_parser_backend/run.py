import sys
import argparse
from app.app import create_app
from app.utils.logger import get_logger
from app.services.vector_db.milvus_connector import MilvusConnector





def main():
    """Run the Flask web server."""
    logger = get_logger(__name__)
    logger.info("Starting Flask server...")
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=4999, use_reloader=False)


if __name__ == "__main__":
    main()
