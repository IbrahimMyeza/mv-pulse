from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request, session, url_for

from database import db
from models.creator_subscription import CreatorSubscription
from models.premium_voice_room import PremiumVoiceRoom
from models.user import User
from models.video import Video
from models.voice_reply import VoiceReply
from models.voice_room_participant import VoiceRoomParticipant
from routes.api_responses import auth_required_response, json_error, json_success
from routes.social_utils import build_reply_tree, current_user, save_video_file
from routes.social_utils import serialize_voice_reply
from services.ai_pipeline import schedule_voice_reply_processing
from services.creator_monetization import (
    creator_earnings_summary,
    ensure_creator_tiers,
    extract_reply_subtree,
    has_subscription_access,
    load_my_rooms,
    notify_monetization_event,
    preview_reply_tree,
    room_access_state,
    room_for_video,
    room_replies,
    serialize_room,
)
from services.payments import (
    activate_subscription_access,
    grant_paid_room_access,
    grant_paid_thread_unlock,
    record_tip_transaction,
)

monetization_bp = Blueprint("monetization", __name__)
ROOM_AUDIO_FOLDER = "static/voices/rooms"


def _auth_required_json(message="Sign in to continue."):
    user = current_user()
    if user:
        return user, None
    return None, auth_required_response(message=message)


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _get_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def _get_room_or_404(room_id):
    return PremiumVoiceRoom.query.get_or_404(room_id)


def _analyze_room_audio(audio_url):
    try:
        from ml.debate_detector import controversy_score
        from ml.transcriber import transcribe_audio
        from ml.voice_sentiment import analyze_voice_sentiment

        transcript = transcribe_audio(audio_url.lstrip("/"))
        sentiment = analyze_voice_sentiment(transcript)
        debate = controversy_score(sentiment, transcript)
        return transcript, sentiment, debate
    except Exception:
        current_app.logger.exception("premium_room.analysis_failed room_audio=%s", audio_url)
        return "", 0.0, 0.0


@monetization_bp.route("/api/creators/<int:user_id>/subscribe", methods=["POST"])
def subscribe_creator(user_id):
    viewer, error = _auth_required_json("Sign in to subscribe.")
    if error:
        return error

    creator = User.query.get_or_404(user_id)
    if creator.id == viewer.id:
        return json_error("cannot subscribe to yourself", status=400)

    data = _get_request_data()
    tiers = ensure_creator_tiers(creator)
    subscription_id = int(data.get("subscription_id")) if data.get("subscription_id") else None
    tier = next((item for item in tiers if item.id == subscription_id), None) if subscription_id else tiers[0]
    if not tier:
        return json_error("subscription tier not found", status=404)

    access = activate_subscription_access(viewer, tier)
    notify_monetization_event(
        recipient_id=creator.id,
        actor_id=viewer.id,
        kind="new_subscriber",
        message=f"{viewer.username} subscribed to {tier.tier_name}",
    )
    return json_success(
        tier_name=tier.tier_name,
        expires_at=access.expires_at.isoformat() if access.expires_at else None,
        founder_badge=access.founder_badge_granted,
    )


@monetization_bp.route("/api/tips", methods=["POST"])
def tip_content():
    viewer, error = _auth_required_json("Sign in to tip creators.")
    if error:
        return error

    data = _get_request_data()
    amount_cents = int(data.get("amount_cents") or 0)
    if amount_cents <= 0:
        return json_error("amount_cents must be positive", status=400)

    target_type = (data.get("target_type") or "video").strip()
    video = None
    voice_reply = None
    room = None
    receiver = None

    if target_type == "video":
        video = Video.query.get_or_404(int(data.get("video_id")))
        receiver = video.creator
    elif target_type == "voice_reply":
        voice_reply = VoiceReply.query.get_or_404(int(data.get("voice_reply_id")))
        receiver = voice_reply.creator
        video = voice_reply.video
    elif target_type == "premium_room":
        room = _get_room_or_404(int(data.get("premium_room_id")))
        receiver = room.creator
        video = room.video
    else:
        return json_error("unsupported tip target", status=400)

    if not receiver or receiver.id == viewer.id:
        return json_error("invalid receiver", status=400)

    transaction = record_tip_transaction(viewer, receiver, amount_cents, video=video, voice_reply=voice_reply, premium_room=room)
    notify_monetization_event(
        recipient_id=receiver.id,
        actor_id=viewer.id,
        kind="tip_received",
        video_id=video.id if video else None,
        voice_reply_id=voice_reply.id if voice_reply else getattr(room, "highlighted_reply_id", None),
        message=f"{viewer.username} sent you a tip",
    )
    return json_success(tip_id=transaction.id, amount_cents=transaction.amount_cents)


@monetization_bp.route("/api/rooms", methods=["POST"])
def create_room():
    creator, error = _auth_required_json("Sign in to create premium rooms.")
    if error:
        return error

    data = _get_request_data()
    title = (data.get("title") or "").strip()
    if not title:
        return json_error("title is required", status=400)

    video_id = int(data.get("video_id")) if data.get("video_id") else None
    highlighted_reply_id = int(data.get("highlighted_reply_id")) if data.get("highlighted_reply_id") else None
    video = Video.query.get(video_id) if video_id else None
    if video and video.creator_id and video.creator_id != creator.id:
        return json_error("you can only monetize your own reels", status=403)
    if highlighted_reply_id:
        reply = VoiceReply.query.get_or_404(highlighted_reply_id)
        if video and reply.video_id != video.id:
            return json_error("highlighted reply must belong to the selected reel", status=400)

    tier_name = (data.get("tier_name") or "Supporter").strip() or "Supporter"
    ensure_creator_tiers(creator)
    room = PremiumVoiceRoom(
        creator_user_id=creator.id,
        video_id=video.id if video else None,
        highlighted_reply_id=highlighted_reply_id,
        title=title,
        description=(data.get("description") or "").strip() or None,
        room_type=(data.get("room_type") or "public").strip() or "public",
        session_kind=(data.get("session_kind") or "debate").strip() or "debate",
        tier_name=tier_name,
        entry_price_cents=int(data.get("entry_price_cents") or 0),
        founder_badges_enabled=str(data.get("founder_badges_enabled") or "false").lower() == "true",
        scheduled_for=_parse_datetime(data.get("scheduled_for")),
        expires_at=_parse_datetime(data.get("expires_at")) or (datetime.utcnow() + timedelta(days=7)),
        participant_cap=int(data.get("participant_cap") or 100),
    )
    db.session.add(room)
    db.session.commit()

    participant = VoiceRoomParticipant(premium_room_id=room.id, user_id=creator.id, role="host", has_paid_entry=True)
    db.session.add(participant)
    db.session.commit()
    return json_success(room=serialize_room(room, creator))


@monetization_bp.route("/api/rooms/<int:room_id>")
def get_room(room_id):
    room = _get_room_or_404(room_id)
    viewer = current_user()
    access = room_access_state(viewer, room) if viewer else room_access_state(None, room)
    serialized_replies = build_reply_tree(room.video_id, viewer=viewer) if room.video_id else []
    room_replies_tree = extract_reply_subtree(serialized_replies, room.highlighted_reply_id) if room.highlighted_reply_id else serialized_replies
    visible_replies = room_replies_tree if access["can_access"] else preview_reply_tree(room_replies_tree, focus_reply_id=room.highlighted_reply_id)
    return json_success(
        room=serialize_room(room, viewer),
        replies=visible_replies,
        preview_only=not access["can_access"],
    )


@monetization_bp.route("/api/rooms/<int:room_id>/join", methods=["POST"])
def join_room(room_id):
    viewer, error = _auth_required_json("Sign in to join premium rooms.")
    if error:
        return error

    room = _get_room_or_404(room_id)
    participant = VoiceRoomParticipant.query.filter_by(premium_room_id=room.id, user_id=viewer.id).first()
    participant_count = room.participants.count()
    if not participant and participant_count >= room.participant_cap:
        return json_error("room participant cap reached", status=403)

    access = room_access_state(viewer, room)
    if room.room_type == "subscriber_only" and not access["can_access"]:
        return json_error("subscription required", status=403, upgrade_cta=access["upgrade_cta"])
    if room.room_type == "paid_entry" and not access["can_access"]:
        grant_paid_room_access(viewer, room, room.entry_price_cents)
        access = room_access_state(viewer, room)
    if room.room_type == "invite_only" and not access["can_access"]:
        return json_error("invite required", status=403, upgrade_cta=access["upgrade_cta"])

    if not participant:
        participant = VoiceRoomParticipant(
            premium_room_id=room.id,
            user_id=viewer.id,
            role="speaker" if room.room_type == "public" else "member",
            has_paid_entry=room.room_type == "paid_entry",
        )
        db.session.add(participant)
    participant.last_seen_at = datetime.utcnow()
    db.session.commit()

    if room.scheduled_for and room.scheduled_for <= datetime.utcnow() + timedelta(hours=1):
        notify_monetization_event(
            recipient_id=viewer.id,
            actor_id=room.creator_user_id,
            kind="room_starting_soon",
            video_id=room.video_id,
            voice_reply_id=room.highlighted_reply_id,
            message=f"{room.title} is starting soon",
        )
    if room.session_kind == "ama" and room.scheduled_for and room.scheduled_for <= datetime.utcnow() + timedelta(minutes=5):
        notify_monetization_event(
            recipient_id=viewer.id,
            actor_id=room.creator_user_id,
            kind="ama_begins_now",
            video_id=room.video_id,
            voice_reply_id=room.highlighted_reply_id,
            message=f"AMA begins now in {room.title}",
        )

    return json_success(room=serialize_room(room, viewer))


@monetization_bp.route("/api/rooms/<int:room_id>/reply", methods=["POST"])
def reply_in_room(room_id):
    viewer, error = _auth_required_json("Sign in to reply in premium rooms.")
    if error:
        return error

    room = _get_room_or_404(room_id)
    access = room_access_state(viewer, room)
    if not access["can_access"]:
        return json_error("room access required", status=403, upgrade_cta=access["upgrade_cta"])

    audio = request.files.get("voice") or request.files.get("audio")
    if not audio or not room.video_id:
        return json_error("audio and linked reel are required", status=400)

    parent_reply_id = request.form.get("parent_reply_id")
    client_token = (request.form.get("client_token") or request.headers.get("X-Idempotency-Key") or "").strip()[:128] or None
    if client_token:
        existing_reply = VoiceReply.query.filter_by(
            video_id=room.video_id,
            user_id=viewer.id,
            client_token=client_token,
        ).first()
        if existing_reply:
            return json_success(
                reply_id=existing_reply.id,
                reply=serialize_voice_reply(existing_reply),
                deduplicated=True,
                target_url=f"/video/{room.video_id}?focus_reply_id={existing_reply.id}#reply-{existing_reply.id}",
            )

    audio_url = save_video_file(audio, ROOM_AUDIO_FOLDER)
    transcript, sentiment, debate = _analyze_room_audio(audio_url)

    reply = VoiceReply(
        video_id=room.video_id,
        user_id=viewer.id,
        parent_reply_id=int(parent_reply_id) if parent_reply_id else room.highlighted_reply_id,
        client_token=client_token,
        audio_url=audio_url,
        duration=float(request.form.get("duration") or 0),
        transcript=transcript,
        language_code=(request.form.get("language_code") or "en").strip() or "en",
        sentiment_score=sentiment,
        controversy_score=debate,
    )
    db.session.add(reply)
    db.session.commit()
    schedule_voice_reply_processing(reply.id)

    participants = room.participants.all()
    for participant in participants:
        if participant.user_id == viewer.id:
            continue
        if viewer.id == room.creator_user_id:
            notify_monetization_event(
                recipient_id=participant.user_id,
                actor_id=viewer.id,
                kind="creator_replied_premium_room",
                video_id=room.video_id,
                voice_reply_id=reply.id,
                message=f"{viewer.username} replied in {room.title}",
            )

    return json_success(
        reply_id=reply.id,
        reply=serialize_voice_reply(reply),
        deduplicated=False,
        target_url=f"/video/{room.video_id}?focus_reply_id={reply.id}#reply-{reply.id}",
    )


@monetization_bp.route("/api/me/rooms")
def my_rooms():
    viewer, error = _auth_required_json("Sign in to see your rooms.")
    if error:
        return error
    return jsonify(load_my_rooms(viewer))


@monetization_bp.route("/api/creator/earnings")
def creator_earnings():
    viewer, error = _auth_required_json("Sign in to see creator earnings.")
    if error:
        return error
    return jsonify(creator_earnings_summary(viewer))