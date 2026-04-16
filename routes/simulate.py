from flask import Blueprint, jsonify
from database import db
from models.reel import Reel
import random

simulate_bp = Blueprint("simulate", __name__)


@simulate_bp.route("/simulate")
def simulate():
    reels = Reel.query.all()

    for reel in reels:
        reel.views += random.randint(10, 100)
        reel.likes += random.randint(1, 20)
        reel.comments += random.randint(0, 5)

    db.session.commit()

    return jsonify({"message": "Live simulation updated"})