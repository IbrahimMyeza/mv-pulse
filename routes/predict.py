from flask import Blueprint, jsonify, request
from models.reel import Reel

predict_bp = Blueprint("predict", __name__)


@predict_bp.route("/predict/<int:reel_id>", methods=["GET"])
def predict_reel(reel_id):
    reel = Reel.query.get_or_404(reel_id)

    virality_score = (
        reel.likes * 3
        + reel.views
        + reel.comments * 2
        + reel.watch_time * 1.5
        + getattr(reel, "debate_score", 0) * 50
    )

    if virality_score > 3000:
        status = "🚀 Going Viral"
    elif virality_score > 2000:
        status = "🔥 Trending"
    else:
        status = "📈 Rising"

    return jsonify({
        "title": reel.title,
        "predicted_virality": virality_score,
        "topic": getattr(reel, "topic", "general"),
        "region": getattr(reel, "region", "Durban"),
        "status": status
    })


@predict_bp.route("/predict", methods=["GET", "POST"])
def predict():
    if request.method == "GET":
        return jsonify({
            "message": "Prediction API active. Use /predict/<reel_id> for DB reels or POST with JSON."
        })

    data = request.get_json()

    likes = data.get("likes", 0)
    views = data.get("views", 0)
    comments = data.get("comments", 0)
    watch_time = data.get("watch_time", 0)
    debate_score = data.get("debate_score", 0)

    virality_score = (
        likes * 3
        + views
        + comments * 2
        + watch_time * 1.5
        + debate_score * 50
    )

    if virality_score > 3000:
        status = "🚀 Going Viral"
    elif virality_score > 2000:
        status = "🔥 Trending"
    else:
        status = "📈 Rising"

    return jsonify({
        "predicted_virality": virality_score,
        "status": status
    })