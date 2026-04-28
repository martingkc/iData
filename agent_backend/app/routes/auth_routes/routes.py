from flask import g, jsonify, request, make_response
from .auth_extensions import basic_auth, token_auth
from ...models.chat_models import User, UserType
from ...db import SessionLocal
from . import auth_bp


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
