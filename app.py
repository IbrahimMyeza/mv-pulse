import os
import time
import uuid
from datetime import timedelta
from http import HTTPStatus

from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
import stripe
from flask_cors import CORS

from flask import Flask, abort, g, render_template, request, send_from_directory, session
from database import db, migrate
from models.user import User
from models.reel import Reel
from models.export_project import ExportProject
from models.creator_subscription import CreatorSubscription
from models.follow import Follow
from models.like import Like
from models.notification import Notification
from models.premium_voice_room import PremiumVoiceRoom
from models.subscriber_access import SubscriberAccess
from models.tip_transaction import TipTransaction
from models.thread_summary import ThreadSummary
from models.text_comment import TextComment
from models.video import Video
from models.save import Save
from models.user_social_profile import UserSocialProfile
from models.voice_embedding import VoiceEmbedding
from models.voice_insight import VoiceInsight
from models.voice_reply import VoiceReply
from models.voice_room_participant import VoiceRoomParticipant

from routes.voice import voice_bp
from routes.auth import auth_bp
from routes.monetization import monetization_bp
from routes.reels import reels_bp
from routes.social import social_bp
from routes.analytics import analytics_bp
from routes.leaderboard import leaderboard_bp
from routes.predict import predict_bp
from routes.controversy import controversy_bp
from routes.dashboard import dashboard_bp
from routes.simulate import simulate_bp
from routes.api_responses import json_error, wants_json_response
from routes.social_utils import ensure_social_seed, hydrate_videos, serialize_video
from services.demo_seed import seed_demo_content
from services.storage import cloud_storage_configured, configured_media_root


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_production_environment():
    return any(
        [
            os.getenv("APP_ENV", "").strip().lower() == "production",
            os.getenv("FLASK_ENV", "").strip().lower() == "production",
            _env_flag("RENDER", default=False),
            bool(os.getenv("RENDER_SERVICE_ID")),
        ]
    )


def _maybe_seed_demo_content():
    if not _env_flag("AUTO_SEED_DEMO_DATA", default=False):
        return

    try:
        result = seed_demo_content()
        if result["reels"] or result["videos"]:
            app.logger.info("demo.seed.complete %s", result)
    except Exception:
        app.logger.exception("demo.seed.failed")


def _database_uri():
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    if database_url:
        return database_url

    if _is_production_environment():
        raise RuntimeError("DATABASE_URL is required in production")

    return (os.getenv("LOCAL_DATABASE_URL") or "sqlite:///mv_pulse.db").strip()


def _validate_production_services():
    if not _is_production_environment():
        return
    if not app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("postgresql"):
        raise RuntimeError("Production requires a PostgreSQL DATABASE_URL")
    if not cloud_storage_configured() and not configured_media_root():
        raise RuntimeError("Production requires CLOUDINARY_URL or MEDIA_STORAGE_ROOT")


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "mv-pulse-dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
}
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 32 * 1024 * 1024))
app.config["SESSION_COOKIE_NAME"] = os.getenv("SESSION_COOKIE_NAME", "mv_pulse_session")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
app.config["SESSION_COOKIE_SECURE"] = _env_flag("SESSION_COOKIE_SECURE", default=_is_production_environment())
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=int(os.getenv("SESSION_DAYS", "30")))
app.config["SESSION_REFRESH_EACH_REQUEST"] = True
app.config["PREFERRED_URL_SCHEME"] = os.getenv("PREFERRED_URL_SCHEME", "https")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
CORS(app, resources={r"/api/*": {"origins": [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()] or ["*"]}})

db.init_app(app)
migrate.init_app(app, db)
_validate_production_services()

app.register_blueprint(voice_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(monetization_bp)
app.register_blueprint(reels_bp)
app.register_blueprint(social_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(predict_bp)
app.register_blueprint(controversy_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(simulate_bp)


@app.before_request
def track_request_start():
    g.request_started_at = time.perf_counter()
    g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    if session.get("user_id"):
        session.permanent = bool(session.get("remember_login", True))


@app.after_request
def log_request(response):
    response.headers["X-Request-ID"] = getattr(g, "request_id", "")
    started_at = getattr(g, "request_started_at", None)
    if started_at is None:
        return response

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    slow_threshold_ms = float(os.getenv("SLOW_REQUEST_MS", "800"))
    log_payload = {
        "request_id": getattr(g, "request_id", None),
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "duration_ms": duration_ms,
    }
    if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR or duration_ms >= slow_threshold_ms:
        app.logger.warning("request.complete %s", log_payload)
    elif response.status_code >= HTTPStatus.BAD_REQUEST:
        app.logger.info("request.client_error %s", log_payload)
    return response


@app.errorhandler(RequestEntityTooLarge)
def handle_large_upload(error):
    app.logger.warning("request.too_large path=%s", request.path)
    if wants_json_response():
        return json_error("upload exceeds size limit", status=413, code="payload_too_large")
    session["auth_message"] = "Upload exceeds the size limit."
    return render_template("index.html", current_user=None, auth_message=session.get("auth_message")), 413

@app.route("/")
def home():
    current_user = None
    user_id = session.get("user_id")
    if user_id:
        current_user = db.session.get(User, user_id)

    ensure_social_seed()
    public_videos = Video.query.filter_by(is_public=True).order_by(Video.created_at.desc()).limit(6).all()
    hydrate_videos(public_videos, viewer=current_user)
    public_video_payloads = [serialize_video(video) for video in public_videos]

    auth_message = session.pop("auth_message", None)

    return render_template(
        "index.html",
        current_user=current_user,
        auth_message=auth_message,
        featured_public_video=public_video_payloads[0] if public_video_payloads else None,
        public_videos=public_video_payloads[1:6] if len(public_video_payloads) > 1 else [],
    )


@app.route("/media/<path:asset_path>")
def media_asset(asset_path):
    media_root = configured_media_root()
    if not media_root:
        abort(404)
    return send_from_directory(media_root, asset_path, conditional=True)


@app.route("/manifest.webmanifest")
def web_manifest():
    return send_from_directory(app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


@app.route("/offline")
def offline_page():
    return send_from_directory(app.static_folder, "offline.html")

with app.app_context():
    _maybe_seed_demo_content()

if __name__ == "__main__":
    app.run(debug=True)