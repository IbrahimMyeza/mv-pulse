import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERIFY_DB = ROOT / "instance" / f"m5_monetization_verify_{os.getpid()}.db"
VERIFY_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB.as_posix()}"
warnings.filterwarnings("ignore", category=DeprecationWarning, message=r"datetime\.datetime\.utcnow\(\) is deprecated")

stub_transcriber = ModuleType("ml.transcriber")
stub_transcriber.transcribe_audio = lambda path: "Premium room verifier transcript"
sys.modules["ml.transcriber"] = stub_transcriber

stub_sentiment = ModuleType("ml.voice_sentiment")
stub_sentiment.analyze_voice_sentiment = lambda transcript: 0.55
sys.modules["ml.voice_sentiment"] = stub_sentiment

stub_debate = ModuleType("ml.debate_detector")
stub_debate.controversy_score = lambda sentiment, transcript: 0.42
sys.modules["ml.debate_detector"] = stub_debate

stub_ranker = ModuleType("ml.ranker")
stub_ranker.rank_reels = lambda videos, preferred_topic=None, preferred_region=None: list(videos)
sys.modules["ml.ranker"] = stub_ranker

stub_reputation = ModuleType("ml.reputation")
stub_reputation.get_creator_score = lambda creator_id: 100
stub_reputation.update_creator_score = lambda creator_id, signal: 100
sys.modules["ml.reputation"] = stub_reputation

from app import app
from database import db
from models.creator_subscription import CreatorSubscription
from models.notification import Notification
from models.subscriber_access import SubscriberAccess
from models.tip_transaction import TipTransaction
from models.user import User
from models.video import Video
from models.voice_reply import VoiceReply
from models.voice_room_participant import VoiceRoomParticipant


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def run_check():
    with app.app_context():
        db.drop_all()
        db.create_all()

        creator = User(username="m5_creator", email="m5_creator@example.com", password="secret123")
        subscriber = User(username="m5_subscriber", email="m5_subscriber@example.com", password="secret123")
        listener = User(username="m5_listener", email="m5_listener@example.com", password="secret123")
        late_user = User(username="m5_late", email="m5_late@example.com", password="secret123")
        db.session.add_all([creator, subscriber, listener, late_user])
        db.session.commit()

        video = Video(
            creator_id=creator.id,
            title="Premium debate reel",
            caption="Testing creator monetization",
            description="M5 verifier fixture",
            video_path="/static/videos/football.mp4",
            topic="civics",
            region="gauteng",
            created_at=datetime.utcnow() - timedelta(minutes=25),
        )
        db.session.add(video)
        db.session.commit()

        root_reply = VoiceReply(
            video_id=video.id,
            user_id=creator.id,
            audio_url="/static/voices/replies/m5-root.wav",
            duration=1.1,
            transcript="Premium root reply",
            created_at=datetime.utcnow() - timedelta(minutes=20),
        )
        child_reply = VoiceReply(
            video_id=video.id,
            user_id=subscriber.id,
            parent_reply=root_reply,
            audio_url="/static/voices/replies/m5-child.wav",
            duration=1.2,
            transcript="Subscriber reply",
            created_at=datetime.utcnow() - timedelta(minutes=15),
        )
        db.session.add_all([root_reply, child_reply])
        db.session.commit()

        creator_client = app.test_client()
        subscriber_client = app.test_client()
        listener_client = app.test_client()
        late_client = app.test_client()
        anonymous_client = app.test_client()

        login_as(creator_client, creator.id)
        login_as(subscriber_client, subscriber.id)
        login_as(listener_client, listener.id)
        login_as(late_client, late_user.id)

        subscribe_response = subscriber_client.post(
            f"/api/creators/{creator.id}/subscribe",
            json={},
            headers={"Accept": "application/json", "X-Requested-With": "fetch"},
        )
        assert subscribe_response.status_code == 200
        subscribe_payload = subscribe_response.get_json()
        assert subscribe_payload["tier_name"]

        tier = CreatorSubscription.query.filter_by(creator_user_id=creator.id).order_by(CreatorSubscription.id.asc()).first()
        assert tier is not None
        access = SubscriberAccess.query.filter_by(subscriber_user_id=subscriber.id, creator_subscription_id=tier.id, access_type="subscription").first()
        assert access is not None
        assert access.expires_at is not None and access.expires_at > datetime.utcnow()

        room_response = creator_client.post(
            "/api/rooms",
            json={
                "title": "Founders AMA",
                "description": "Subscriber-only voice room",
                "video_id": video.id,
                "highlighted_reply_id": root_reply.id,
                "room_type": "subscriber_only",
                "session_kind": "ama",
                "tier_name": tier.tier_name,
                "participant_cap": 4,
                "scheduled_for": (datetime.utcnow() + timedelta(minutes=4)).isoformat(),
            },
            headers={"Accept": "application/json", "X-Requested-With": "fetch"},
        )
        assert room_response.status_code == 200
        room_payload = room_response.get_json()["room"]
        room_id = room_payload["id"]

        locked_room = anonymous_client.get(f"/api/rooms/{room_id}")
        assert locked_room.status_code == 200
        locked_payload = locked_room.get_json()
        assert locked_payload["preview_only"] is True
        assert len(locked_payload["replies"]) == 1

        join_for_subscriber = subscriber_client.post(f"/api/rooms/{room_id}/join", headers={"Accept": "application/json", "X-Requested-With": "fetch"})
        assert join_for_subscriber.status_code == 200

        denied_listener = listener_client.post(f"/api/rooms/{room_id}/join", headers={"Accept": "application/json", "X-Requested-With": "fetch"})
        assert denied_listener.status_code == 403
        assert denied_listener.get_json()["upgrade_cta"] == "Subscribe to join this room"

        paid_room_response = creator_client.post(
            "/api/rooms",
            json={
                "title": "Paid debate room",
                "description": "Pay-per-entry thread",
                "video_id": video.id,
                "highlighted_reply_id": root_reply.id,
                "room_type": "paid_entry",
                "session_kind": "debate",
                "entry_price_cents": 1500,
                "participant_cap": 2,
            },
            headers={"Accept": "application/json", "X-Requested-With": "fetch"},
        )
        assert paid_room_response.status_code == 200
        paid_room_id = paid_room_response.get_json()["room"]["id"]

        paid_join = listener_client.post(f"/api/rooms/{paid_room_id}/join", headers={"Accept": "application/json", "X-Requested-With": "fetch"})
        assert paid_join.status_code == 200

        cap_reached = late_client.post(f"/api/rooms/{paid_room_id}/join", headers={"Accept": "application/json", "X-Requested-With": "fetch"})
        assert cap_reached.status_code == 403
        assert b"participant cap reached" in cap_reached.data

        tip_response = listener_client.post(
            "/api/tips",
            json={
                "target_type": "video",
                "video_id": video.id,
                "amount_cents": 750,
            },
            headers={"Accept": "application/json", "X-Requested-With": "fetch"},
        )
        assert tip_response.status_code == 200
        assert TipTransaction.query.count() == 1

        room_page = anonymous_client.get(f"/video/{video.id}?focus_reply_id={root_reply.id}")
        assert room_page.status_code == 200
        assert b"Join the room or subscribe to unlock the full conversation" in room_page.data
        assert b"Tip creator" in room_page.data

        profile_page = subscriber_client.get(f"/profile/{creator.username}")
        assert profile_page.status_code == 200
        assert b"Subscribe to" in profile_page.data
        assert tier.tier_name.encode() in profile_page.data

        earnings_response = creator_client.get("/api/creator/earnings", headers={"Accept": "application/json", "X-Requested-With": "fetch"})
        assert earnings_response.status_code == 200
        earnings_payload = earnings_response.get_json()
        assert earnings_payload["total_earnings_cents"] >= tier.monthly_price_cents + 1500 + 750
        assert earnings_payload["top_supporters"]

        notification_kinds = {row.kind for row in Notification.query.all()}
        assert "new_subscriber" in notification_kinds
        assert "tip_received" in notification_kinds
        assert "room_starting_soon" in notification_kinds or "ama_begins_now" in notification_kinds

        print("subscription_tier", subscribe_payload["tier_name"])
        print("subscriber_access_active", True)
        print("paid_room_joined", VoiceRoomParticipant.query.filter_by(premium_room_id=paid_room_id).count())
        print("tip_transactions", TipTransaction.query.count())
        print("total_earnings_cents", earnings_payload["total_earnings_cents"])
        print("notification_kinds", sorted(notification_kinds))
        print("m5_monetization_status", "ok")


if __name__ == "__main__":
    run_check()