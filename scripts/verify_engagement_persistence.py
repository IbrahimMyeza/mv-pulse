import os
import sys
from io import BytesIO
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERIFY_DB = ROOT / "instance" / f"engagement_verify_{os.getpid()}.db"
VERIFY_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB.as_posix()}"

stub_transcriber = ModuleType("ml.transcriber")
stub_transcriber.transcribe_audio = lambda path: "Recorded via verifier"
sys.modules["ml.transcriber"] = stub_transcriber

stub_sentiment = ModuleType("ml.voice_sentiment")
stub_sentiment.analyze_voice_sentiment = lambda transcript: 0.35
sys.modules["ml.voice_sentiment"] = stub_sentiment

stub_debate = ModuleType("ml.debate_detector")
stub_debate.controversy_score = lambda sentiment, transcript: 0.12
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
from models.notification import Notification
from models.user import User
from models.video import Video
from models.voice_reply import VoiceReply


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def run_check():
    with app.app_context():
        db.drop_all()
        db.create_all()

        creator = User(username="creator", email="creator@example.com", password="secret123")
        listener = User(username="listener", email="listener@example.com", password="secret123")
        db.session.add_all([creator, listener])
        db.session.commit()

        video = Video(
            creator_id=creator.id,
            title="Engagement test video",
            caption="Reply with voice.",
            description="Verification fixture",
            video_path="/static/videos/football.mp4",
            likes=0,
            shares_count=0,
            voice_replies=0,
        )
        db.session.add(video)
        db.session.commit()

        reply = VoiceReply(
            video_id=video.id,
            user_id=creator.id,
            audio_url="/static/voices/replies/original.wav",
            duration=1.1,
            transcript="Original voice reply",
        )
        db.session.add(reply)
        db.session.commit()

        client = app.test_client()

        anonymous_follow = client.post(f"/api/follow/{creator.id}")
        assert anonymous_follow.status_code == 401

        anonymous_video = client.get(f"/video/{video.id}")
        assert anonymous_video.status_code == 200
        assert b"Sign in to record" in anonymous_video.data

        login_as(client, listener.id)

        follow_on = client.post(f"/api/follow/{creator.id}")
        assert follow_on.status_code == 200
        assert follow_on.get_json()["following"] is True

        follow_off = client.delete(f"/api/follow/{creator.id}")
        assert follow_off.status_code == 200
        assert follow_off.get_json()["following"] is False

        follow_again = client.post(f"/api/follow/{creator.id}")
        assert follow_again.status_code == 200
        assert follow_again.get_json()["followers"] == 1

        profile_page = client.get(f"/profile/{creator.username}")
        assert profile_page.status_code == 200
        assert b"Following" in profile_page.data

        video_like_on = client.post(f"/api/videos/{video.id}/like")
        assert video_like_on.status_code == 200
        assert video_like_on.get_json()["liked"] is True

        video_like_off = client.post(f"/api/videos/{video.id}/like")
        assert video_like_off.status_code == 200
        assert video_like_off.get_json()["liked"] is False

        legacy_video_like = client.post(f"/api/video/{video.id}/like")
        assert legacy_video_like.status_code == 200
        assert legacy_video_like.get_json()["liked"] is True

        reply_like_on = client.post(f"/api/voice-replies/{reply.id}/like")
        assert reply_like_on.status_code == 200
        assert reply_like_on.get_json()["liked"] is True

        reply_like_off = client.post(f"/api/voice-replies/{reply.id}/like")
        assert reply_like_off.status_code == 200
        assert reply_like_off.get_json()["liked"] is False

        save_on = client.post(f"/api/videos/{video.id}/save")
        assert save_on.status_code == 200
        assert save_on.get_json()["saved"] is True

        save_off = client.post(f"/api/videos/{video.id}/save")
        assert save_off.status_code == 200
        assert save_off.get_json()["saved"] is False

        share = client.post(f"/api/videos/{video.id}/share")
        assert share.status_code == 200
        assert share.get_json()["shares_count"] == 1

        legacy_share = client.post(f"/api/video/{video.id}/share")
        assert legacy_share.status_code == 200
        assert legacy_share.get_json()["shares_count"] == 2

        authenticated_video = client.get(f"/video/{video.id}")
        assert authenticated_video.status_code == 200
        assert b"Record voice reply" in authenticated_video.data

        reply_post = client.post(
            "/voice/reply",
            data={
                "video_id": str(video.id),
                "language_code": "en",
                "duration": "2.5",
                "voice": (BytesIO(b"voice-bytes"), "reply.wav"),
            },
            headers={"Accept": "application/json", "X-Requested-With": "fetch"},
            content_type="multipart/form-data",
        )
        assert reply_post.status_code == 200

        voice_notifications = Notification.query.filter(Notification.kind.in_(["follow", "video_like", "voice_reply_like", "voice_reply"])).count()
        assert voice_notifications >= 3

        print("follow_post", follow_again.status_code, follow_again.get_json()["followers"])
        print("video_like_compat", legacy_video_like.status_code, legacy_video_like.get_json()["likes"])
        print("voice_reply_like", reply_like_off.status_code, reply_like_off.get_json()["likes_count"])
        print("save_toggle", save_off.status_code, save_off.get_json()["saved"])
        print("share_tracking", legacy_share.status_code, legacy_share.get_json()["shares_count"])
        print("voice_reply_post", reply_post.status_code)
        print("notification_fanout", voice_notifications)
        print("engagement_status", "ok")


if __name__ == "__main__":
    run_check()