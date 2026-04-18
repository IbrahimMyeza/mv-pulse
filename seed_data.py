from app import app
from services.demo_seed import seed_demo_content


if __name__ == "__main__":
    with app.app_context():
        result = seed_demo_content()
        if result["reels"]:
            print("Demo reels inserted successfully.")
        else:
            print("Demo reels already exist. Skipping seed.")

        if result["videos"]:
            print("Demo videos inserted successfully.")
        else:
            print("Demo videos already exist. Skipping social seed.")