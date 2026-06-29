import os
import re

from flask import Blueprint, redirect, request, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from models.user import User
from database import db
from routes.api_responses import auth_required_response, json_error, json_success, wants_json_response

auth_bp = Blueprint("auth", __name__)
oauth = OAuth()


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def _generate_username(name, email):
    base = re.sub(r"[^a-z0-9]", "", (name or email.split("@")[0]).lower())
    base = base[:20] or "user"
    username, n = base, 1
    while User.query.filter_by(username=username).first():
        username = f"{base}{n}"
        n += 1
    return username


def _wants_json_response():
    return wants_json_response()


def _remember_login(payload):
    raw_value = payload.get("remember_me")
    if raw_value is None:
        return True
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


def _login_user(user, remember_login=True):
    session.permanent = remember_login
    session["user_id"] = user.id
    session["username"] = user.username
    session["email"] = user.email
    session["remember_login"] = remember_login


def _auth_success_response(message, user):
    if _wants_json_response():
        return json_success(
            message=message,
            user={
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
        )

    return redirect(url_for("dashboard.dashboard"))


def _auth_error_response(message, status_code):
    if _wants_json_response():
        if status_code == 401:
            return auth_required_response(message=message, status=status_code)
        return json_error(message, status=status_code)

    session["auth_message"] = message
    return redirect(url_for("home"))

@auth_bp.route("/signup", methods=["POST"])
def signup():
    payload = request.get_json(silent=True) or request.form
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    password_confirmation = payload.get("password_confirmation") or payload.get("confirm_password") or ""

    if not username or not email or not password:
        return _auth_error_response("username, email, and password are required", 400)

    if len(password) < 8:
        return _auth_error_response("password must be at least 8 characters", 400)

    if password != password_confirmation:
        return _auth_error_response("passwords do not match", 400)

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return _auth_error_response("account already exists, sign in instead", 409)

    hashed_password = generate_password_hash(password)
    remember_login = _remember_login(payload)

    user = User(username=username, email=email, password=hashed_password)
    db.session.add(user)
    db.session.commit()
    _login_user(user, remember_login=remember_login)

    return _auth_success_response("secure user created", user)

@auth_bp.route("/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or request.form
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    remember_login = _remember_login(payload)

    user = User.query.filter_by(email=email).first()

    if user and user.password and check_password_hash(user.password, password):
        _login_user(user, remember_login=remember_login)
        return _auth_success_response("login success", user)

    if user and not user.password:
        return _auth_error_response("this account uses Google sign-in", 401)

    return _auth_error_response("invalid credentials", 401)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()

    if _wants_json_response():
        return json_success(message="logout success")

    return redirect(url_for("home"))


@auth_bp.route("/auth/google")
def google_login():
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/google/callback")
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        session["auth_message"] = "Google sign-in was cancelled or failed."
        return redirect(url_for("home"))

    info = token.get("userinfo") or {}
    google_id = info.get("sub")
    email = (info.get("email") or "").lower().strip()
    name = info.get("name") or info.get("given_name") or ""
    avatar_url = info.get("picture")

    if not google_id or not email:
        session["auth_message"] = "Could not retrieve your Google account details."
        return redirect(url_for("home"))

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            user.google_id = google_id
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
        else:
            user = User(
                username=_generate_username(name, email),
                email=email,
                password=None,
                google_id=google_id,
                avatar_url=avatar_url,
            )
            db.session.add(user)
        db.session.commit()

    _login_user(user)
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.route("/api/auth/session", methods=["GET"])
def auth_session():
    user_id = session.get("user_id")
    if not user_id:
        return json_success(authenticated=False, user=None)

    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return json_success(authenticated=False, user=None)

    return json_success(
        authenticated=True,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    )