from flask import Blueprint, jsonify, redirect, request, url_for

from database import db
from models.video import Video
from routes.social_utils import save_video_file

reels_bp = Blueprint("reels", __name__)
VIDEO_FOLDER = "static/uploads/videos"


@reels_bp.route("/upload_reel", methods=["POST"])
def upload_reel():
    title = request.form.get("title")
    video = request.files.get("video")

    if not title or not video:
        return jsonify({"error": "title and video required"}), 400

    video_url = save_video_file(video, VIDEO_FOLDER)
    video_row = Video(title=title, caption=title, description=title, video_path=video_url)
    db.session.add(video_row)
    db.session.commit()

    return jsonify({"message": "video uploaded", "video_id": video_row.id, "title": title})


@reels_bp.route("/like/<int:video_id>", methods=["POST"])
def like_reel(video_id):
    video = Video.query.get_or_404(video_id)
    video.likes += 1
    db.session.commit()
    return redirect(url_for("social.video_detail", id=video.id))


@reels_bp.route("/comment/<int:video_id>", methods=["POST"])
def comment_reel(video_id):
    return redirect(url_for("social.video_detail", id=video_id))


@reels_bp.route("/watch/<int:video_id>", methods=["POST"])
def watch_reel(video_id):
    video = Video.query.get_or_404(video_id)
    watch_seconds = int(request.form.get("seconds", 0))
    video.views += 1
    video.watch_time += watch_seconds
    db.session.commit()
    return jsonify({"message": "watch tracked", "views": video.views, "watch_time": video.watch_time})


@reels_bp.route("/agree/<int:video_id>", methods=["POST"])
def agree_reel(video_id):
    return redirect(url_for("social.video_detail", id=video_id))


@reels_bp.route("/disagree/<int:video_id>", methods=["POST"])
def disagree_reel(video_id):
    video = Video.query.get_or_404(video_id)
    video.debate_score += 0.3
    db.session.commit()
    return redirect(url_for("social.video_detail", id=video.id))
