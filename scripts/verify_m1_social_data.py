import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERIFY_DB = ROOT / "instance" / "m1_social_verify.db"
VERIFY_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB.as_posix()}"

from app import app
from database import db
from models.follow import Follow
from models.like import Like
from models.notification import Notification
from models.reel import Reel
from models.save import Save
from models.user import User
from models.user_social_profile import UserSocialProfile
from models.video import Video
from models.voice_reply import VoiceReply


def run_check():
    with app.app_context():
        db.drop_all()
        db.create_all()

        user = User(username="m1_architect", email="m1@example.com", password="secret123")
        viewer = User(username="m1_listener", email="listener@example.com", password="secret123")
        db.session.add_all([user, viewer])
        db.session.commit()

        profile = UserSocialProfile(
            user_id=user.id,
            display_name="M1 Architect",
            headline="Voice-first builder",
            bio="Verifying additive social data layer",
        )
        reel = Reel(title="Legacy reel survives", video_path="static/videos/football.mp4")
        video = Video(
            creator_id=user.id,
            title="Umbono Wami test video",
            caption="Reply with your voice.",
            description="M1 verification record",
            video_path="/static/videos/football.mp4",
        )
        db.session.add_all([profile, reel, video])
        db.session.commit()

        root_reply = VoiceReply(
            video_id=video.id,
            user_id=viewer.id,
            audio_url="/static/voices/test-reply.wav",
            duration=4.2,
            transcript="Voice replies are live.",
        )
        db.session.add(root_reply)
        db.session.commit()

        follow = Follow(follower_id=viewer.id, followed_id=user.id)
        video_like = Like(user_id=viewer.id, video_id=video.id)
        reply_like = Like(user_id=user.id, voice_reply_id=root_reply.id)
        reel_save = Save(user_id=viewer.id, reel_id=reel.id)
        video_save = Save(user_id=user.id, video_id=video.id)
        notification = Notification(
            recipient_user_id=user.id,
            actor_user_id=viewer.id,
            video_id=video.id,
            voice_reply_id=root_reply.id,
            kind="voice_reply",
            message="m1_listener replied with a voice note.",
        )
        db.session.add_all([follow, video_like, reply_like, reel_save, video_save, notification])
        db.session.commit()

        assert UserSocialProfile.query.count() == 1
        assert Reel.query.count() == 1
        assert VoiceReply.query.count() == 1
        assert Follow.query.count() == 1
        assert Notification.query.count() == 1
        assert Like.query.count() == 2
        assert Save.query.count() == 2
        assert user.social_profile.display_name == "M1 Architect"
        assert video.likes.count() == 1
        assert video.saves.count() == 1
        assert root_reply.likes.count() == 1
        assert reel.saves.count() == 1

        print("m1_social_profile", UserSocialProfile.query.count())
        print("m1_reels", Reel.query.count())
        print("m1_voice_replies", VoiceReply.query.count())
        print("m1_follows", Follow.query.count())
        print("m1_notifications", Notification.query.count())
        print("m1_likes", Like.query.count())
        print("m1_saves", Save.query.count())
        print("m1_status", "ok")


if __name__ == "__main__":
    run_check()