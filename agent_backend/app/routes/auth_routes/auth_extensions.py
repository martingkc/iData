from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth
from flask import jsonify, make_response, g, request

from ...models.chat_models import User
from ...db import SessionLocal

basic_auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth(scheme="Bearer")


@basic_auth.error_handler
def unauthorized():
    response = make_response(jsonify({"error": "Unauthorized access"}), 401)
    response.headers.pop("WWW-Authenticate", None)
    return response


@basic_auth.verify_password
def verify_password(email, password):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email).first()
        if not user or not user.verify_password(password):
            db.close()
            return False
        g.user = user
        g.db = db  # Keep session alive for the request, closed by teardown
        return True
    except Exception:
        db.close()
        return False

@token_auth.verify_token
def verify_token(token=None):
    # Attempt to get the access token from cookies if not provided explicitly
    if token is None or token == "":
        token = request.cookies.get("access_token")

    if not token:
        return False

    db = SessionLocal()
    try:
        user = User.verify_auth_token_with_session(token, db)
        if not user:
            db.close()
            return False
        g.user = user
        g.db = db  # Keep session alive for the request, closed by teardown
        return True
    except Exception:
        db.close()
        return False