import json
import time

from flask import g, jsonify, request, make_response, redirect, current_app
import jwt

from .auth_extensions import basic_auth, token_auth
from ...models.chat_models import User, UserType, UserGoogleToken
from ...db import SessionLocal
from ...config.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    FRONTEND_URL,
)

from google_auth_oauthlib.flow import Flow

from . import auth_bp

_GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _build_google_flow(state: str | None = None):

    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [GOOGLE_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    kwargs: dict = {"redirect_uri": GOOGLE_REDIRECT_URI}
    if state:
        kwargs["state"] = state
    return Flow.from_client_config(client_config, scopes=_GOOGLE_CALENDAR_SCOPES, **kwargs)


@auth_bp.route("/signup", methods=["POST"])
def signup():
    """
    Register a new user account.
    
    Request body (JSON):
        email: str (required)
        password: str (required)
        name: str (required)
        surname: str (required)
    """
    data = request.get_json(force=True) or {}
    
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()
    surname = (data.get("surname") or "").strip()
    
    # Validation
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if not surname:
        return jsonify({"error": "Surname is required"}), 400
    
    db = SessionLocal()
    try:
        # Check if user already exists
        existing = db.query(User).filter_by(email=email).first()
        if existing:
            return jsonify({"error": "Email already registered"}), 409
        
        # Create new user
        user = User(
            name=name,
            surname=surname,
            email=email,
            password=password,
            user_type=UserType.BASE,
        )
        db.add(user)
        db.commit()
        
        # Auto-login: generate tokens
        access_token = user.generate_auth_token(600)
        refresh_token = user.generate_auth_token(24 * 3600)
        
        response = make_response(jsonify({
            "message": "Account created successfully",
            "user": {
                "email": user.email,
                "name": user.name,
                "surname": user.surname,
            }
        }), 201)
        
        response.set_cookie(
            "access_token",
            access_token,
            httponly=True,
            secure=False,
            samesite="Lax",
            max_age=600,
        )
        response.set_cookie(
            "refresh_token",
            refresh_token,
            httponly=True,
            secure=False,
            samesite="Lax",
            max_age=24 * 3600,
        )
        return response
    except Exception as e:
        db.rollback()
        return jsonify({"error": "Failed to create account"}), 500
    finally:
        db.close()


@auth_bp.route("/login", methods=["POST"])
@basic_auth.login_required
def login():
    # Set the max age of the refresh token based on the user type for security reasons (3 hours for admins, 24 hours for others)
    if g.user.user_type == UserType.ADMIN:
        refresh_hours = 3
    else:
        refresh_hours = 24
    
    # Generate tokens: access token (10 minutes) and refresh token (based on user type)
    access_token = g.user.generate_auth_token(600)  # 600 seconds = 10 minutes
    refresh_token = g.user.generate_auth_token(refresh_hours * 3600)

    # Create a response and set the tokens as HttpOnly cookies
    response = make_response(jsonify({"message": "Logged in successfully"}))

    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=False,
        samesite="Lax",
        max_age=600,
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=False,
        samesite="Lax",
        max_age=refresh_hours * 3600,
    )
    return response





@auth_bp.route("/refresh", methods=["POST"])
def refresh_token_httponly():
    """
    Refresh the access token using the refresh token cookie.
    This endpoint does NOT require a valid access token - it uses the refresh token instead.
    """
    # Retrieve the refresh token from the cookie
    refresh_token_cookie = request.cookies.get("refresh_token")
    if not refresh_token_cookie:
        return jsonify({"error": "No refresh token provided"}), 401
    
    user = User.verify_auth_token(refresh_token_cookie)
    if not user:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    # Generate a new access token valid for 10 minutes
    new_access_token = user.generate_auth_token(600)
    response = make_response(jsonify({"message": "Token refreshed"}))
    response.set_cookie(
        "access_token",
        new_access_token,
        httponly=True,
        secure=False,
        samesite="Lax",
        max_age=600,
    )
    return response


@auth_bp.route("/logout", methods=["POST"])
def logout():
    response = make_response(jsonify({"message": "Logged out"}))
    response.set_cookie("access_token", "", expires=0)
    response.set_cookie("refresh_token", "", expires=0)
    return response


@auth_bp.route("/get_token", methods=["GET"])
@basic_auth.login_required
def get_auth_token():
    # Generate an access token valid for 10 minutes
    access_token = g.user.generate_auth_token(600)
    # Generate a refresh token valid for 1 day

    if g.user.user_type == UserType.ADMIN:
        max_hr = 1
    else:
        max_hr = 24

    refresh_token = g.user.generate_auth_token(max_hr * 3600)
    return jsonify(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access_duration": 600,
        }
    )


@auth_bp.route("/refresh_token", methods=["POST"])
@token_auth.login_required
def refresh_token():
    """
    Refresh the access token using a valid refresh token.
    This endpoint expects the client to send the refresh token.
    Once verified by token_auth.verify_token, the endpoint issues a new access token.
    """
    new_access_token = g.user.generate_auth_token(600)
    return jsonify({"access_token": new_access_token, "access_duration": 600})


@auth_bp.route("/user", methods=["POST"])
@token_auth.login_required
def get_user():
    """
    This endpoint returns the user information for the currently authenticated user.

    Returns:
        Response: A JSON response containing the user data.
    """
    user = g.user
    response = jsonify(
        {
            "email": user.email,
            "name": user.name,
            "surname": user.surname,
        }
    )
    return response


# ---------------------------------------------------------------------------
# Google Calendar OAuth endpoints
# ---------------------------------------------------------------------------

@auth_bp.route("/google/calendar", methods=["GET"])
@token_auth.login_required
def google_calendar_auth():
    """Return the Google OAuth consent URL for the current user."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return jsonify({"error": "Google OAuth is not configured on this server."}), 503

    # Encode user_id in a short-lived signed state token (CSRF protection).
    state = jwt.encode(
        {"user_id": str(g.user.id), "exp": time.time() + 600},
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    flow = _build_google_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",
    )
    return jsonify({"auth_url": auth_url})


@auth_bp.route("/google/calendar/callback", methods=["GET"])
def google_calendar_callback():
    """Handle the redirect back from Google, exchange code for tokens, store them."""
    error = request.args.get("error")
    if error:
        return redirect(f"{FRONTEND_URL}?calendar_error={error}")

    state = request.args.get("state", "")
    code = request.args.get("code", "")

    # Verify state JWT and recover user_id.
    try:
        data = jwt.decode(state, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        user_id = data["user_id"]
    except Exception:
        return redirect(f"{FRONTEND_URL}?calendar_error=invalid_state")

    try:
        flow = _build_google_flow(state=state)
        # google-auth-oauthlib validates the state internally; pass the full URL.
        flow.fetch_token(code=code)
        creds = flow.credentials
    except Exception as exc:
        return redirect(f"{FRONTEND_URL}?calendar_error=token_exchange_failed")

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or _GOOGLE_CALENDAR_SCOPES),
    }

    db = SessionLocal()
    try:
        existing = (
            db.query(UserGoogleToken)
            .filter_by(user_id=user_id, service="google_calendar")
            .first()
        )
        if existing:
            existing.token_json = json.dumps(token_data)
            existing.updated_at = __import__("datetime").datetime.utcnow()
        else:
            db.add(
                UserGoogleToken(
                    user_id=user_id,
                    service="google_calendar",
                    token_json=json.dumps(token_data),
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        return redirect(f"{FRONTEND_URL}?calendar_error=db_error")
    finally:
        db.close()

    return redirect(f"{FRONTEND_URL}?calendar_connected=true")


@auth_bp.route("/google/calendar/status", methods=["GET"])
@token_auth.login_required
def google_calendar_status():
    """Return whether the current user has connected Google Calendar."""
    db = g.db
    token = (
        db.query(UserGoogleToken)
        .filter_by(user_id=g.user.id, service="google_calendar")
        .first()
    )
    return jsonify({"connected": token is not None})


@auth_bp.route("/google/calendar/disconnect", methods=["POST"])
@token_auth.login_required
def google_calendar_disconnect():
    """Remove the stored Google Calendar token for the current user."""
    db = g.db
    token = (
        db.query(UserGoogleToken)
        .filter_by(user_id=g.user.id, service="google_calendar")
        .first()
    )
    if token:
        db.delete(token)
        db.commit()
    return jsonify({"message": "Google Calendar disconnected."})
