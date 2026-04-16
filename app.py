import os
import stripe

from flask import Flask, render_template, session
from database import db
from models.user import User
from models.reel import Reel
from models.export_project import ExportProject
from models.follow import Follow
from models.like import Like
from models.notification import Notification
from models.video import Video
from models.save import Save
from models.user_social_profile import UserSocialProfile
from models.voice_reply import VoiceReply

from routes.voice import voice_bp
from routes.auth import auth_bp
from routes.reels import reels_bp
from routes.social import social_bp
from routes.analytics import analytics_bp
from routes.leaderboard import leaderboard_bp
from routes.predict import predict_bp
from routes.controversy import controversy_bp
from routes.dashboard import dashboard_bp
from routes.simulate import simulate_bp


def _database_uri():
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url or "sqlite:///mv_pulse.db"


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "mv-pulse-dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

db.init_app(app)

app.register_blueprint(voice_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(reels_bp)
app.register_blueprint(social_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(predict_bp)
app.register_blueprint(controversy_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(simulate_bp)

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