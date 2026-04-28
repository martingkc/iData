from flask import Blueprint

file_bp = Blueprint("file_bp", __name__)

# Import routes so decorators register endpoints
from . import file_routes  # noqa: F401,E402
