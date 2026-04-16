from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from models.follow import Follow
from models.user import User
from models.video import Video
from models.voice_reply import VoiceReply
from services.social_engagement import (
    follow_payload,
    toggle_follow,
    toggle_video_like,
    toggle_video_save,
    toggle_voice_reply_like,
    track_video_share,
)
from routes.social_utils import (
    current_user,
    ensure_social_seed,
    serialize_video,
    social_context,
    build_reply_tree,
    hydrate_videos,
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


def _auth_response(message):
    return jsonify({"error": message, "login_url": url_for("home")}), 401


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


@social_bp.route("/api/follow/<int:user_id>", methods=["POST", "DELETE"])
def api_follow_user(user_id):
    viewer, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to follow creators.")

    target_user = User.query.get_or_404(user_id)
    if viewer.id == target_user.id:
        return jsonify({"error": "cannot follow yourself"}), 400

    relation_exists = Follow.query.filter_by(follower_id=viewer.id, followed_id=target_user.id).first() is not None
    if request.method == "POST" and not relation_exists:
        state = toggle_follow(viewer, target_user)
    elif request.method == "DELETE" and relation_exists:
        state = toggle_follow(viewer, target_user)
    else:
        state = {
            "following": relation_exists,
            "followers": target_user.followers.count(),
            "following_count": viewer.following.count(),
        }

    return jsonify(follow_payload(viewer, target_user, state))


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
    viewer = current_user()
    hydrate_videos([video], viewer=viewer)
    context = social_context(active_tab="home", selected_video=video)
    return render_template(
        "video.html",
        video=video,
        video_payload=serialize_video(video),
        replies=build_reply_tree(video.id, viewer=viewer),
        current_user=viewer,
        locale_options=context["locale_options"],
    )


@social_bp.route("/api/video/<int:id>/replies")
def api_video_replies(id):
    Video.query.get_or_404(id)
    return jsonify({"replies": build_reply_tree(id, viewer=current_user())})


@social_bp.route("/api/videos/<int:id>/like", methods=["POST"])
def api_videos_like(id):
    viewer, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to like videos.")

    video = Video.query.get_or_404(id)
    return jsonify(toggle_video_like(viewer, video))


@social_bp.route("/api/video/<int:id>/like", methods=["POST"])
def api_like_video(id):
    return api_videos_like(id)


@social_bp.route("/api/videos/<int:id>/save", methods=["POST"])
def api_videos_save(id):
    viewer, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to save videos.")

    video = Video.query.get_or_404(id)
    return jsonify(toggle_video_save(viewer, video))


@social_bp.route("/api/videos/<int:id>/share", methods=["POST"])
def api_videos_share(id):
    video = Video.query.get_or_404(id)
    return jsonify(track_video_share(video))


@social_bp.route("/api/video/<int:id>/share", methods=["POST"])
def api_share_video(id):
    return api_videos_share(id)


@social_bp.route("/api/voice-replies/<int:id>/like", methods=["POST"])
def api_voice_replies_like(id):
    viewer, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to like voice replies.")

    voice_reply = VoiceReply.query.get_or_404(id)
    return jsonify(toggle_voice_reply_like(viewer, voice_reply))


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

    state = toggle_follow(viewer, profile_user)
    if request.is_json:
        return jsonify(follow_payload(viewer, profile_user, state))
    return redirect(url_for("social.profile", username=profile_user.username))


@social_bp.route("/notifications")
def notifications():
    user, error = _auth_required_redirect()
    if error:
        return error

    user.notifications.update({"is_read": True})
    db.session.commit()
    return render_template("notifications.html", **social_context(active_tab="notifications", profile_user=user))
