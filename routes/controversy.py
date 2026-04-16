from flask import Blueprint, jsonify
from models.reel import Reel

controversy_bp = Blueprint("controversy", __name__)


@controversy_bp.route("/controversy")
def controversy():
    reels = Reel.query.order_by(
        (Reel.disagree_count - Reel.agree_count).desc()
    ).all()

    data = [
        {
            "title": reel.title,
            "controversy_score": reel.disagree_count - reel.agree_count,
            "topic": reel.topic,
            "region": reel.region
        }
        for reel in reels
    ]

    return jsonify(data)