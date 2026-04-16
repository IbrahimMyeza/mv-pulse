from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from database import db
from models.follow import Follow
from models.user import User
from models.video import Video
from models.voice_reply import VoiceReply
from routes.social_utils import (
    create_notification,
    current_user,
    ensure_social_seed,
    follow_state,
    serialize_video,
    social_context,
    build_reply_tree,
    save_video_file,
)

social_bp = Blueprint("social", __name__)
VIDEO_FOLDER = "static/uploads/videos"


def _auth_required_json():
    user = current_user()
    if user:
        return user, None
    return None, (jsonify({"error": "authentication required"}), 401)


def _auth_required_redirect():
    user = current_user()
    if user:
        return user, None
    session["auth_message"] = "Sign in to continue."
    return None, redirect(url_for("home"))


@social_bp.route("/feed")
def feed():
    return render_template("dashboard.html", **social_context(active_tab="home"))


@social_bp.route("/api/feed")
def api_feed():
    context = social_context(active_tab="home")
    return jsonify({
        "videos": context["feed_videos"],
        "featured_video": context["featured_video"],
        "locale_options": context["locale_options"],
    })


@social_bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        context = social_context(active_tab="upload")
        return render_template("dashboard.html", **context)

    user, error = _auth_required_redirect()
    if error:
        return error

    title = (request.form.get("title") or "").strip()
    caption = (request.form.get("caption") or "").strip()
    topic = (request.form.get("topic") or "general").strip() or "general"
    region = (request.form.get("region") or "Durban").strip() or "Durban"
    language_code = (request.form.get("language_code") or "en").strip() or "en"
    video_file = request.files.get("video")

    if not title or not video_file:
        session["auth_message"] = "Video title and file are required."
        return redirect(url_for("social.upload"))

    video_url = save_video_file(video_file, VIDEO_FOLDER)
    video = Video(
        creator_id=user.id,
        title=title,
        caption=caption,
        description=caption,
        video_path=video_url,
        topic=topic,
        region=region,
        category=topic,
        language_code=language_code,
        transcript_summary=caption,
    )
    db.session.add(video)
    db.session.commit()

    return redirect(url_for("social.video_detail", id=video.id))


@social_bp.route("/video/<int:id>")
def video_detail(id):
    ensure_social_seed()
    video = Video.query.get_or_404(id)
    context = social_context(active_tab="home", selected_video=video)
    return render_template(
        "video.html",
        video=video,
        video_payload=serialize_video(video),
        replies=build_reply_tree(video.id),
        current_user=current_user(),
        locale_options=context["locale_options"],
    )


@social_bp.route("/api/video/<int:id>/replies")
def api_video_replies(id):
    Video.query.get_or_404(id)
    return jsonify({"replies": build_reply_tree(id)})


@social_bp.route("/api/video/<int:id>/like", methods=["POST"])
def api_like_video(id):
    video = Video.query.get_or_404(id)
    video.likes += 1
    db.session.commit()
    return jsonify({"likes": video.likes})


@social_bp.route("/api/video/<int:id>/share", methods=["POST"])
def api_share_video(id):
    video = Video.query.get_or_404(id)
    video.shares_count += 1
    db.session.commit()
    return jsonify({"shares_count": video.shares_count})


@social_bp.route("/profile/<username>")
def profile(username):
    profile_user = User.query.filter_by(username=username).first_or_404()
    return render_template("profile.html", **social_context(active_tab="profile", profile_user=profile_user))


@social_bp.route("/api/profile/<username>/follow", methods=["POST"])
def follow_profile(username):
    viewer, error = _auth_required_json()
    if error:
        if request.is_json:
            return error
        session["auth_message"] = "Sign in to follow creators."
        return redirect(url_for("home"))

    profile_user = User.query.filter_by(username=username).first_or_404()
    if viewer.id == profile_user.id:
        return jsonify({"error": "cannot follow yourself"}), 400

    relation = Follow.query.filter_by(follower_id=viewer.id, followed_id=profile_user.id).first()
    if relation:
        db.session.delete(relation)
        db.session.commit()
        if request.is_json:
            return jsonify({"following": False, "followers": profile_user.followers.count()})
        return redirect(url_for("social.profile", username=profile_user.username))

    relation = Follow(follower_id=viewer.id, followed_id=profile_user.id)
    db.session.add(relation)
    db.session.commit()
    create_notification(
        recipient_id=profile_user.id,
        actor_id=viewer.id,
        kind="follow",
        message=f"{viewer.username} followed you",
    )
    if request.is_json:
        return jsonify({"following": True, "followers": profile_user.followers.count()})
    return redirect(url_for("social.profile", username=profile_user.username))


@social_bp.route("/notifications")
def notifications():
    user, error = _auth_required_redirect()
    if error:
        return error

    user.notifications.update({"is_read": True})
    db.session.commit()
    return render_template("notifications.html", **social_context(active_tab="notifications", profile_user=user))
