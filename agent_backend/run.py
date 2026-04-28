import os
from app.db import  init_db
from flask import Flask
from app.routes.chat_routes import chat_bp
from app import create_app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)