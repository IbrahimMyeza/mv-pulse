from flask import Blueprint, request, jsonify, render_template, redirect
from models.reel import Reel
from database import db
from ml.ranker import rank_reels
from ml.personalizer import learn_preferences
from ml.diversity import diversify_feed
import os

reels_bp = Blueprint("reels", __name__)
VIDEO_FOLDER = "static/videos"


@reels_bp.route("/upload_reel", methods=["POST"])
def upload_reel():
    title = request.form.get("title")
    video = request.files.get("video")

    if not title or not video:
        return jsonify({"error": "title and video required"}), 400

    os.makedirs(VIDEO_FOLDER, exist_ok=True)

    file_path = os.path.join(VIDEO_FOLDER, video.filename)
    video.save(file_path)

    reel = Reel(title=title, video_path=file_path)
    db.session.add(reel)
    db.session.commit()

    return jsonify({"message": "reel uploaded", "title": title})


@reels_bp.route("/feed", methods=["GET"])
def feed():
    reels = Reel.query.all()

    preferred_topic = "sports"
    preferred_region = "Durban"

    ranked_reels = rank_reels(
        reels,
        preferred_topic=preferred_topic,
        preferred_region=preferred_region
    )

    final_feed = diversify_feed(ranked_reels, preferred_topic)

    return render_template("feed.html", reels=final_feed)


@reels_bp.route("/like/<int:reel_id>", methods=["POST"])
def like_reel(reel_id):
    reel = Reel.query.get_or_404(reel_id)
    reel.likes += 1
    db.session.commit()
    return redirect("/feed")


@reels_bp.route("/comment/<int:reel_id>", methods=["POST"])
def comment_reel(reel_id):
    reel = Reel.query.get_or_404(reel_id)
    reel.comments += 1
    reel.debate_score += 0.2
    db.session.commit()
    return redirect("/feed")


@reels_bp.route("/watch/<int:reel_id>", methods=["POST"])
def watch_reel(reel_id):
    reel = Reel.query.get_or_404(reel_id)
    watch_seconds = int(request.form.get("seconds", 0))

    reel.views += 1
    reel.watch_time += watch_seconds
    db.session.commit()

    return jsonify({
        "message": "watch tracked",
        "views": reel.views,
        "watch_time": reel.watch_time
    })


@reels_bp.route("/agree/<int:reel_id>", methods=["POST"])
def agree_reel(reel_id):
    reel = Reel.query.get_or_404(reel_id)
    reel.agree_count += 1
    db.session.commit()
    return redirect("/feed")


@reels_bp.route("/disagree/<int:reel_id>", methods=["POST"])
def disagree_reel(reel_id):
    reel = Reel.query.get_or_404(reel_id)
    reel.disagree_count += 1
    reel.debate_score += 0.3
    db.session.commit()
    return redirect("/feed")


@reels_bp.route("/export_dataset")
def export_dataset():
    export_reels_dataset()
    return "dataset exported successfully"