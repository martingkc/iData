
from flask import Blueprint


chat_bp = Blueprint("chat_bp", __name__)

# Import route definitions so the decorators run and register endpoints.
from . import chat_routes  # noqa: F401,E402