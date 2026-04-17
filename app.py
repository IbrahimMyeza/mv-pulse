import os
import time
import uuid
from http import HTTPStatus

from werkzeug.exceptions import RequestEntityTooLarge
import stripe

from flask import Flask, g, render_template, request, session
from database import db
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


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database_uri():
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url or "sqlite:///mv_pulse.db"


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "mv-pulse-dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 32 * 1024 * 1024))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
app.config["SESSION_COOKIE_SECURE"] = _env_flag("SESSION_COOKIE_SECURE", default=False)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

db.init_app(app)

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

    auth_message = session.pop("auth_message", None)

    return render_template("index.html", current_user=current_user, auth_message=auth_message)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)