from flask import Blueprint, jsonify
from models.reel import Reel

leaderboard_bp = Blueprint("leaderboard", __name__)


@leaderboard_bp.route("/leaderboard")
def leaderboard():
    reels = Reel.query.order_by(Reel.views.desc()).limit(5).all()

    data = [
        {
            "title": reel.title,
            "views": reel.views,
            "likes": reel.likes,
            "topic": reel.topic,
            "region": reel.region
        }
        for reel in reels
    ]

    return jsonify(data)