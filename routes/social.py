from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from database import db
from models.follow import Follow
from models.user import User
from models.video import Video
from models.voice_insight import VoiceInsight
from models.voice_reply import VoiceReply
from services.ai_pipeline import ensure_processed_for_video
from services.clip_engine import suggest_clips_for_video
from services.social_engagement import (
    follow_payload,
    toggle_follow,
    toggle_video_like,
    toggle_video_save,
    toggle_voice_reply_save,
    toggle_voice_reply_like,
    track_video_share,
)
from services.thread_intelligence import get_thread_summary, search_discovery
from services.voice_identity import voice_identity_payload
from services.creator_monetization import (
    apply_supporter_badges,
    ensure_creator_tiers,
    extract_reply_subtree,
    preview_reply_tree,
    room_access_state,
    room_for_video,
    serialize_room,
    serialize_subscription_tier,
)
from services.social_retention import (
    load_activity,
    load_liked_videos,
    load_my_voice_replies,
    load_saved_replies,
    load_saved_videos,
    mark_notifications_read,
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
from services.thread_heat import record_reply_listen

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
    return render_template(
        "dashboard.html",
        **social_context(
            active_tab="home",
            discovery_query=request.args.get("q", "").strip() or None,
            discovery_topic=request.args.get("topic", "").strip() or None,
            discovery_tone=request.args.get("tone", "").strip() or None,
        ),
    )


@social_bp.route("/api/feed")
def api_feed():
    context = social_context(
        active_tab="home",
        discovery_query=request.args.get("q", "").strip() or None,
        discovery_topic=request.args.get("topic", "").strip() or None,
        discovery_tone=request.args.get("tone", "").strip() or None,
    )
    return jsonify({
        "videos": context["feed_videos"],
        "feed_items": context["feed_items"],
        "hot_threads": context["hot_threads"],
        "featured_video": context["featured_video"],
        "discovery_results": context["discovery_results"],
        "locale_options": context["locale_options"],
        "notifications_unread_count": context["notifications_unread_count"],
    })


@social_bp.route("/api/me/saved/videos")
def api_me_saved_videos():
    user, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to see saved videos.")
    return jsonify({"items": load_saved_videos(user)})


@social_bp.route("/api/me/saved/replies")
def api_me_saved_replies():
    user, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to see saved replies.")
    return jsonify({"items": load_saved_replies(user)})


@social_bp.route("/api/me/voice-replies")
def api_me_voice_replies():
    user, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to see your voice replies.")
    return jsonify({"items": load_my_voice_replies(user)})


@social_bp.route("/api/me/activity")
def api_me_activity():
    user, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to see your activity.")
    return jsonify({"items": load_activity(user)})


@social_bp.route("/api/me/likes")
def api_me_likes():
    user, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to see liked videos.")
    return jsonify({"items": load_liked_videos(user)})


@social_bp.route("/api/notifications/read", methods=["POST"])
def api_notifications_read():
    user, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to manage notifications.")

    payload = request.get_json(silent=True) or {}
    unread_count = mark_notifications_read(user, notification_ids=payload.get("notification_ids"))
    return jsonify({"unread_count": unread_count})


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
    focused_reply_id = request.args.get("focus_reply_id", type=int)
    ensure_processed_for_video(video.id)
    hydrate_videos([video], viewer=viewer)
    context = social_context(active_tab="home", selected_video=video)
    serialized_replies = build_reply_tree(video.id, viewer=viewer)
    premium_room = room_for_video(video.id, focused_reply_id)
    premium_access = None
    video_creator_tiers = []
    if video.creator:
        video_creator_tiers = [serialize_subscription_tier(tier, viewer=viewer) for tier in ensure_creator_tiers(video.creator)]
    if premium_room:
        premium_access = room_access_state(viewer, premium_room) if viewer else room_access_state(None, premium_room)
        serialized_replies = extract_reply_subtree(serialized_replies, premium_room.highlighted_reply_id) if premium_room.highlighted_reply_id else serialized_replies
        if not premium_access["can_access"]:
            serialized_replies = preview_reply_tree(serialized_replies, focus_reply_id=premium_room.highlighted_reply_id)

    serialized_replies = apply_supporter_badges(serialized_replies, video.creator_id or 0)
    clip_suggestions = suggest_clips_for_video(
        video,
        insights_by_reply_id={row.voice_reply_id: row for row in VoiceInsight.query.join(VoiceReply, VoiceReply.id == VoiceInsight.voice_reply_id).filter(VoiceReply.video_id == video.id).all()},
    )
    return render_template(
        "video.html",
        video=video,
        video_payload=serialize_video(video),
        replies=serialized_replies,
        current_user=viewer,
        locale_options=context["locale_options"],
        focused_reply_id=focused_reply_id,
        premium_room=serialize_room(premium_room, viewer) if premium_room else None,
        premium_preview_only=bool(premium_room and premium_access and not premium_access["can_access"]),
        creator_tiers=video_creator_tiers,
        thread_summary=get_thread_summary(video.id),
        clip_suggestions=clip_suggestions,
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


@social_bp.route("/api/voice-replies/<int:id>/listen", methods=["POST"])
def api_voice_replies_listen(id):
    VoiceReply.query.get_or_404(id)
    return jsonify({"replay_listens": record_reply_listen(id)})


@social_bp.route("/api/voice-replies/<int:id>/save", methods=["POST"])
def api_voice_replies_save(id):
    viewer, error = _auth_required_json()
    if error:
        return _auth_response("Sign in to save voice replies.")

    voice_reply = VoiceReply.query.get_or_404(id)
    return jsonify(toggle_voice_reply_save(viewer, voice_reply))


@social_bp.route("/profile/<username>")
def profile(username):
    profile_user = User.query.filter_by(username=username).first_or_404()
    return render_template("profile.html", **social_context(active_tab="profile", profile_user=profile_user))


@social_bp.route("/api/profile/<username>/voice-identity")
def api_profile_voice_identity(username):
    profile_user = User.query.filter_by(username=username).first_or_404()
    return jsonify(voice_identity_payload(profile_user))


@social_bp.route("/api/thread/<int:video_id>/summary")
def api_thread_summary(video_id):
    Video.query.get_or_404(video_id)
    ensure_processed_for_video(video_id)
    return jsonify(get_thread_summary(video_id) or {})


@social_bp.route("/api/discovery")
def api_discovery():
    return jsonify({
        "items": search_discovery(
            query=request.args.get("q", "").strip() or None,
            topic=request.args.get("topic", "").strip() or None,
            tone=request.args.get("tone", "").strip() or None,
        )
    })


@social_bp.route("/api/videos/<int:id>/clip-suggestions")
def api_clip_suggestions(id):
    video = Video.query.get_or_404(id)
    ensure_processed_for_video(video.id)
    return jsonify({"items": suggest_clips_for_video(video)})


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
    return render_template("dashboard.html", **social_context(active_tab="notifications", profile_user=user))
