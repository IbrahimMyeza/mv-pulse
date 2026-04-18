from flask import Blueprint, redirect, request, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from models.user import User
from database import db
from routes.api_responses import auth_required_response, json_error, json_success, wants_json_response

auth_bp = Blueprint("auth", __name__)


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

    if user and check_password_hash(user.password, password):
        _login_user(user, remember_login=remember_login)
        return _auth_success_response("login success", user)

    return _auth_error_response("invalid credentials", 401)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()

    if _wants_json_response():
        return json_success(message="logout success")

    return redirect(url_for("home"))


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