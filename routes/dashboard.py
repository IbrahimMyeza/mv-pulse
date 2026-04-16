import stripe
from flask import Blueprint, render_template, send_file, redirect, url_for, session
from models.reel import Reel

dashboard_bp = Blueprint("dashboard", __name__)


def _num(value, default=0):
    return value if value is not None else default


def _get_num(obj, name, default=0):
    return _num(getattr(obj, name, default), default)


def _get_text(obj, name, default=""):
    value = getattr(obj, name, default)
    return value if value else default


def _controversy_score(reel):
    return _get_num(reel, "disagree_count") - _get_num(reel, "agree_count")


def _viral_score(reel):
    return (
        _get_num(reel, "likes") * 2
        + _get_num(reel, "comments") * 3
        + _get_num(reel, "debate_score") * 10
        + (_get_num(reel, "views") / 100)
    )


def _creator_score(reel):
    return (
        _get_num(reel, "creator_score")
        + _get_num(reel, "likes")
        + _get_num(reel, "comments")
        + (_get_num(reel, "views") / 100)
    )


@dashboard_bp.route("/upgrade")
def upgrade():
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": "MV Pulse Pro"
                },
                "unit_amount": 999,
                "recurring": {
                    "interval": "month"
                }
            },
            "quantity": 1
        }],
        mode="subscription",
        success_url=url_for("dashboard.upgrade_success", _external=True),
        cancel_url=url_for("dashboard.dashboard", _external=True)
    )
    return redirect(checkout_session.url)


@dashboard_bp.route("/upgrade/success")
def upgrade_success():
    session["is_pro_user"] = True
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/dashboard")
def dashboard():
    reels = Reel.query.all()

    total_reels = len(reels)
    total_views = sum(_get_num(r, "views") for r in reels)
    total_likes = sum(_get_num(r, "likes") for r in reels)

    chart_labels = [_get_text(r, "title", "Untitled Reel") for r in reels]
    chart_likes = [_get_num(r, "likes") for r in reels]
    chart_controversy = [_controversy_score(r) for r in reels]

    top_controversial = sorted(
        reels,
        key=_controversy_score,
        reverse=True
    )[:5]

    topic_counts = {}
    for reel in reels:
        topic = _get_text(reel, "topic", "general")
        topic_counts[topic] = topic_counts.get(topic, 0) + 1

    region_counts = {}
    for reel in reels:
        region = _get_text(reel, "region", "Durban")
        region_counts[region] = region_counts.get(region, 0) + 1

    hottest_region = "No data"
    hottest_value = 0
    if region_counts:
        hottest_region = max(region_counts, key=region_counts.get)
        hottest_value = region_counts[hottest_region]

    breakout_reel = None
    breakout_views = 0
    if reels:
        breakout_reel = max(reels, key=lambda r: _get_num(r, "views"))
        breakout_views = _get_num(breakout_reel, "views")

    predicted_next_topic = "none"
    if topic_counts:
        predicted_next_topic = max(topic_counts, key=topic_counts.get)

    top_viral_reel = None
    top_viral_score = 0
    for reel in reels:
        score = _viral_score(reel)
        if score > top_viral_score:
            top_viral_score = score
            top_viral_reel = reel

    ranked_reels = sorted(reels, key=_viral_score, reverse=True)
    creator_leaderboard = sorted(reels, key=_creator_score, reverse=True)

    creator_region_scores = {}
    for reel in reels:
        region = _get_text(reel, "region", "Durban")
        creator_region_scores[region] = (
            creator_region_scores.get(region, 0) + _creator_score(reel)
        )

    network_nodes = []
    for index, reel in enumerate(reels):
        network_nodes.append({
            "x": index + 1,
            "y": _get_num(reel, "creator_score") + _get_num(reel, "likes"),
            "label": f"{_get_text(reel, 'topic', 'general')} - {_get_text(reel, 'region', 'Durban')}"
        })

    flow_timeline_labels = []
    flow_timeline_values = []
    for index, reel in enumerate(reels):
        flow_timeline_labels.append(f"T{index + 1}")
        flow_timeline_values.append(
            _get_num(reel, "likes")
            + _get_num(reel, "comments")
            + _get_num(reel, "debate_score") * 10
        )

    forecast_labels = flow_timeline_labels[:]
    forecast_values = flow_timeline_values[:]

    best_post_slot = "now"
    if forecast_values:
        best_index = forecast_values.index(max(forecast_values))
        best_post_slot = forecast_labels[best_index]

    ticker_alerts = [
        f"🚨 {hottest_region} hotspot rising",
        f"🌡️ Top controversy: {_get_text(top_controversial[0], 'title', 'none') if top_controversial else 'none'}",
        f"🔥 Total platform views: {total_views}",
        f"📍 Dominant topic: {predicted_next_topic}",
    ]

    content_copilot = (
        f"Post about {predicted_next_topic} "
        f"in {hottest_region} during {best_post_slot}"
    )

    ai_caption = (
        f"🔥 {hottest_region} is talking about "
        f"{predicted_next_topic} right now — what’s your take?"
    )

    ai_hook = (
        f"🎥 {hottest_region} can't stop talking about "
        f"{predicted_next_topic} — here's why."
    )

    ai_script = (
        f"{ai_hook} "
        f"Right now {hottest_region} is seeing strong momentum around "
        f"{predicted_next_topic}. "
        f"This could become the next major breakout conversation. "
        f"What do you think Durban should do next?"
    )

    ai_voiceover = (
        f"{ai_hook} "
        f"Pause. "
        f"Right now in {hottest_region}, "
        f"people are heavily engaged around {predicted_next_topic}. "
        f"This may be the next big breakout in the city. "
        f"Drop your thoughts below."
    )

    ai_shotlist = [
        f"Shot 1: Opening close-up text hook about {predicted_next_topic}",
        f"Shot 2: B-roll of {hottest_region} streets or landmarks",
        "Shot 3: Overlay stats showing topic momentum spike",
        "Shot 4: Final CTA screen asking viewers to comment"
    ]

    ai_thumbnail = (
        f"{hottest_region.upper()} CAN'T STOP "
        f"TALKING ABOUT {predicted_next_topic.upper()}"
    )

    export_pack = {
        "copilot": content_copilot,
        "caption": ai_caption,
        "hook": ai_hook,
        "script": ai_script,
        "voiceover": ai_voiceover,
        "shotlist": ai_shotlist,
        "thumbnail": ai_thumbnail
    }

    workspace = {
        "name": "Durban Media Team",
        "members": 5,
        "plan": "Pro Team"
    }

    command_center = {
        "region": hottest_region,
        "topic": predicted_next_topic,
        "slot": best_post_slot,
        "plan": workspace["plan"]
    }

    is_pro_user = session.get("is_pro_user", False)

    team_comments = [
        "Thumbnail needs stronger rivalry wording",
        "Post this before evening football traffic",
        "Use voiceover version for faceless reels"
    ]

    live_alerts = [
        "🔥 Sports momentum spike detected in Durban",
        "💬 New team comment added to export pack",
        "⏰ Posting window F4 is approaching",
        "📈 Debate score crossed high-risk threshold"
    ]

    autonomous_status = {
        "state": "ACTIVE",
        "last_action": f"Generated full pack for {predicted_next_topic} in {hottest_region}"
    }

    return render_template(
        "dashboard.html",
        total_reels=total_reels,
        total_views=total_views,
        total_likes=total_likes,
        top_controversial=top_controversial,
        hottest_region=hottest_region,
        hottest_value=hottest_value,
        breakout_reel=breakout_reel,
        breakout_views=breakout_views,
        predicted_next_topic=predicted_next_topic,
        top_viral_reel=top_viral_reel,
        top_viral_score=round(top_viral_score, 2),
        ranked_reels=ranked_reels[:5],
        creator_leaderboard=creator_leaderboard[:5],
        chart_labels=chart_labels,
        chart_likes=chart_likes,
        chart_controversy=chart_controversy,
        topic_labels=list(topic_counts.keys()),
        topic_values=list(topic_counts.values()),
        region_labels=list(region_counts.keys()),
        region_values=list(region_counts.values()),
        creator_region_labels=list(creator_region_scores.keys()),
        creator_region_values=list(creator_region_scores.values()),
        network_nodes=network_nodes,
        forecast_labels=forecast_labels,
        forecast_values=forecast_values,
        best_post_slot=best_post_slot,
        flow_timeline_labels=flow_timeline_labels,
        flow_timeline_values=flow_timeline_values,
        ticker_alerts=ticker_alerts,
        content_copilot=content_copilot,
        ai_caption=ai_caption,
        ai_hook=ai_hook,
        ai_script=ai_script,
        ai_voiceover=ai_voiceover,
        ai_shotlist=ai_shotlist,
        ai_thumbnail=ai_thumbnail,
        export_pack=export_pack,
        is_pro_user=is_pro_user,
        workspace=workspace,
        command_center=command_center,
        team_comments=team_comments,
        live_alerts=live_alerts,
        autonomous_status=autonomous_status
    )


@dashboard_bp.route("/download-pack")
def download_pack():
    return send_file(
        "static/exports/mv_pulse_creator_brief.pdf",
        as_attachment=True
    )


@dashboard_bp.route("/tv")
def tv_mode():
    return dashboard()