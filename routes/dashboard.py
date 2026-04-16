import json
from io import BytesIO

import stripe
from flask import Blueprint, jsonify, render_template, request, send_file, redirect, url_for, session
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from database import db
from models.export_project import ExportProject
from models.reel import Reel
from models.user import User

dashboard_bp = Blueprint("dashboard", __name__)


def _num(value, default=0):
    return value if value is not None else default


def _get_num(obj, name, default=0):
    return _num(getattr(obj, name, default), default)


def _get_text(obj, name, default=""):
    value = getattr(obj, name, default)
    return value if value else default


def _safe_round(value, digits=2):
    return round(value, digits) if value is not None else 0


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def _serialize_project(project):
    payload = {}
    if project.payload:
        try:
            payload = json.loads(project.payload)
        except json.JSONDecodeError:
            payload = {}

    created_at = project.created_at.isoformat() if project.created_at else None

    return {
        "id": project.id,
        "title": project.title,
        "kind": project.kind,
        "status": project.status,
        "created_at": created_at,
        "payload": payload,
    }


def _save_project(user, payload, kind="draft", status="saved"):
    title = (payload.get("title") or payload.get("topic") or "Untitled Project").strip()
    project = ExportProject(
        user_id=user.id,
        title=title,
        kind=kind,
        status=status,
        payload=json.dumps(payload),
    )
    db.session.add(project)
    db.session.commit()
    return project


def _require_user_json():
    user = _current_user()
    if user:
        return user, None
    return None, (jsonify({"error": "authentication required"}), 401)


def _serialize_reel(reel):
    return {
        "id": reel.id,
        "title": _get_text(reel, "title", "Untitled Reel"),
        "region": _get_text(reel, "region", "Durban"),
        "topic": _get_text(reel, "topic", "general"),
        "views": _get_num(reel, "views"),
        "likes": _get_num(reel, "likes"),
        "comments": _get_num(reel, "comments"),
        "creator_score": _safe_round(_get_num(reel, "creator_score")),
        "debate_score": _safe_round(_get_num(reel, "debate_score")),
        "controversy_score": _safe_round(_controversy_score(reel)),
        "viral_score": _safe_round(_viral_score(reel)),
    }


def _build_export_summary(reels):
    topic_counts = {}
    region_counts = {}

    for reel in reels:
        topic = _get_text(reel, "topic", "general")
        region = _get_text(reel, "region", "Durban")
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        region_counts[region] = region_counts.get(region, 0) + 1

    hottest_region = max(region_counts, key=region_counts.get) if region_counts else "No data"
    predicted_next_topic = max(topic_counts, key=topic_counts.get) if topic_counts else "none"

    return {
        "hottest_region": hottest_region,
        "predicted_next_topic": predicted_next_topic,
        "best_post_slot": "now",
        "total_reels": len(reels),
        "total_views": sum(_get_num(r, "views") for r in reels),
        "top_title": _get_text(reels[0], "title", "No featured reel") if reels else "No featured reel",
    }


def _billing_unavailable_response():
    return (
        "<h1>Billing is not configured yet.</h1>"
        "<p>Add STRIPE_SECRET_KEY in Render, then redeploy and try again.</p>"
        f"<p><a href=\"{url_for('dashboard.dashboard')}\">Return to dashboard</a></p>",
        503,
    )


def _build_creator_brief_pdf(summary):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    text = pdf.beginText(50, 750)
    text.setFont("Helvetica-Bold", 16)
    text.textLine("MV Pulse Creator Brief")
    text.setFont("Helvetica", 11)
    text.textLine("")

    lines = [
        f"Hotspot: {summary['hottest_region']}",
        f"Topic: {summary['predicted_next_topic']}",
        f"Best slot: {summary['best_post_slot']}",
        f"Total reels: {summary['total_reels']}",
        f"Total views: {summary['total_views']}",
        f"Featured reel: {summary['top_title']}",
        "",
        "Recommended caption:",
        f"{summary['hottest_region']} is talking about {summary['predicted_next_topic']} right now.",
        "",
        "Suggested hook:",
        f"Why {summary['hottest_region']} cannot stop talking about {summary['predicted_next_topic']}.",
    ]

    for line in lines:
        text.textLine(line)

    pdf.drawText(text)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


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


def _build_mobile_composer(topic, region, title=None, cta=None):
    active_topic = title or topic or "Durban trend"
    active_region = region or "Durban"
    active_cta = cta or "Drop your take below"

    return {
        "title": active_topic,
        "caption": (
            f"{active_region} is already reacting to {active_topic}. "
            f"Here is the fast breakdown creators should post on right now. {active_cta}."
        ),
        "hook": f"Why {active_region} creators cannot ignore {active_topic} tonight.",
        "cta": active_cta,
        "voiceover": (
            f"Quick pulse check: {active_region} is heating up around {active_topic}. "
            f"Use this angle, move fast, and {active_cta.lower()}."
        ),
        "hashtags": [
            f"#{active_region.replace(' ', '')}",
            f"#{str(active_topic).replace(' ', '')}",
            "#MVPulse",
            "#CreatorIntel",
            "#TrendWatch",
        ],
    }


def _build_dashboard_context():
    user = _current_user()
    reels = Reel.query.all()
    saved_projects = []
    if user:
        saved_projects = ExportProject.query.filter_by(user_id=user.id).order_by(ExportProject.created_at.desc()).limit(8).all()

    total_reels = len(reels)
    total_views = sum(_get_num(r, "views") for r in reels)
    total_likes = sum(_get_num(r, "likes") for r in reels)
    total_comments = sum(_get_num(r, "comments") for r in reels)

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
        f"Hotspot rising in {hottest_region}",
        f"Top controversy: {_get_text(top_controversial[0], 'title', 'none') if top_controversial else 'none'}",
        f"Total platform views: {total_views}",
        f"Dominant topic: {predicted_next_topic}",
    ]

    content_copilot = (
        f"Post about {predicted_next_topic} "
        f"in {hottest_region} during {best_post_slot}"
    )

    ai_caption = (
        f"{hottest_region} is talking about "
        f"{predicted_next_topic} right now. What's your take?"
    )

    ai_hook = (
        f"{hottest_region} can't stop talking about "
        f"{predicted_next_topic}. Here's why."
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
        "Sports momentum spike detected in Durban",
        "New team comment added to export pack",
        "Posting window F4 is approaching",
        "Debate score crossed high-risk threshold"
    ]

    autonomous_status = {
        "state": "ACTIVE",
        "last_action": f"Generated full pack for {predicted_next_topic} in {hottest_region}"
    }

    avg_creator_score = (
        sum(_creator_score(reel) for reel in reels) / total_reels if total_reels else 0
    )
    engagement_velocity = total_likes + total_comments + (total_views / 25 if total_views else 0)
    viral_probability = min(99, int(top_viral_score * 5) + 24) if top_viral_score else 18
    brand_score = min(99, int(avg_creator_score * 8) + 32) if avg_creator_score else 41
    creator_growth_streak = max(3, min(21, len(saved_projects) + total_reels + len(topic_counts))) if (total_reels or saved_projects) else 3

    mobile_home_kpis = [
        {"label": "Viral probability", "value": f"{viral_probability}%", "tone": "accent"},
        {"label": "Hot region", "value": hottest_region, "tone": "warm"},
        {"label": "Views velocity", "value": str(int(engagement_velocity)), "tone": "cool"},
        {"label": "Creator streak", "value": f"{creator_growth_streak}d", "tone": "accent"},
    ]

    home_trends = [
        {
            "title": _get_text(reel, "title", "Untitled Reel"),
            "meta": f"{_get_text(reel, 'topic', 'general')} in {_get_text(reel, 'region', 'Durban')}",
            "score": f"{_safe_round(_viral_score(reel))} pulse",
        }
        for reel in ranked_reels[:4]
    ]

    controversy_watch = [
        {
            "title": _get_text(reel, "title", "Untitled Reel"),
            "score": _safe_round(_controversy_score(reel)),
            "warning": "High debate pressure" if _controversy_score(reel) > 0 else "Conversation stable",
        }
        for reel in top_controversial[:3]
    ]

    analytics_cards = [
        {"label": "24h views", "value": total_views},
        {"label": "Engagement velocity", "value": int(engagement_velocity)},
        {"label": "Viral score", "value": _safe_round(top_viral_score)},
        {"label": "Brand score", "value": brand_score},
    ]

    schedule_plan = {
        "best_post_slot": best_post_slot,
        "timezone": "Africa/Johannesburg",
        "next_reminder": f"15 minutes before {best_post_slot}",
        "queue": [
            {"name": "Trend alert breakdown", "time": best_post_slot, "status": "Ready"},
            {"name": "Voiceover remix", "time": "Tonight 19:30", "status": "Draft"},
            {"name": "Comment reply clip", "time": "Tomorrow 08:00", "status": "Needs assets"},
        ],
    }

    profile_summary = {
        "username": user.username if user else "Guest Creator",
        "email": user.email if user else "Sign in to unlock project history",
        "brand_score": brand_score,
        "saved_exports": len([project for project in saved_projects if project.kind == "export"]),
        "saved_drafts": len([project for project in saved_projects if project.kind == "draft"]),
        "workspace_team": workspace["members"],
        "subscription_tier": "Pro" if is_pro_user else "Free",
        "daily_generation_limit": "Unlimited" if is_pro_user else "3/day",
        "authenticated": bool(user),
    }

    composer_defaults = _build_mobile_composer(
        predicted_next_topic,
        hottest_region,
        title=breakout_reel.title if breakout_reel else predicted_next_topic,
        cta="Comment your strategy below",
    )

    return {
        "current_user": user,
        "total_reels": total_reels,
        "total_views": total_views,
        "total_likes": total_likes,
        "top_controversial": top_controversial,
        "hottest_region": hottest_region,
        "hottest_value": hottest_value,
        "breakout_reel": breakout_reel,
        "breakout_views": breakout_views,
        "predicted_next_topic": predicted_next_topic,
        "top_viral_reel": top_viral_reel,
        "top_viral_score": _safe_round(top_viral_score),
        "ranked_reels": ranked_reels[:5],
        "creator_leaderboard": creator_leaderboard[:5],
        "chart_labels": chart_labels,
        "chart_likes": chart_likes,
        "chart_controversy": chart_controversy,
        "topic_labels": list(topic_counts.keys()),
        "topic_values": list(topic_counts.values()),
        "region_labels": list(region_counts.keys()),
        "region_values": list(region_counts.values()),
        "creator_region_labels": list(creator_region_scores.keys()),
        "creator_region_values": list(creator_region_scores.values()),
        "network_nodes": network_nodes,
        "forecast_labels": forecast_labels,
        "forecast_values": forecast_values,
        "best_post_slot": best_post_slot,
        "flow_timeline_labels": flow_timeline_labels,
        "flow_timeline_values": flow_timeline_values,
        "ticker_alerts": ticker_alerts,
        "content_copilot": content_copilot,
        "ai_caption": ai_caption,
        "ai_hook": ai_hook,
        "ai_script": ai_script,
        "ai_voiceover": ai_voiceover,
        "ai_shotlist": ai_shotlist,
        "ai_thumbnail": ai_thumbnail,
        "export_pack": export_pack,
        "is_pro_user": is_pro_user,
        "workspace": workspace,
        "command_center": command_center,
        "team_comments": team_comments,
        "live_alerts": live_alerts,
        "autonomous_status": autonomous_status,
        "mobile_home_kpis": mobile_home_kpis,
        "home_trends": home_trends,
        "controversy_watch": controversy_watch,
        "analytics_cards": analytics_cards,
        "schedule_plan": schedule_plan,
        "profile_summary": profile_summary,
        "composer_defaults": composer_defaults,
        "viral_probability": viral_probability,
        "engagement_velocity": int(engagement_velocity),
        "brand_score": brand_score,
        "creator_growth_streak": creator_growth_streak,
        "saved_projects": [_serialize_project(project) for project in saved_projects],
    }


@dashboard_bp.route("/upgrade")
def upgrade():
    if not stripe.api_key:
        return _billing_unavailable_response()

    try:
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
    except stripe.StripeError:
        return _billing_unavailable_response()

    return redirect(checkout_session.url)


@dashboard_bp.route("/upgrade/success")
def upgrade_success():
    session["is_pro_user"] = True
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/dashboard")
def dashboard():
    return redirect(url_for("social.feed"))


@dashboard_bp.route("/api/creator/feed")
def api_feed():
    context = _build_dashboard_context()
    return jsonify({
        "command_center": context["command_center"],
        "ticker_alerts": context["ticker_alerts"],
        "live_alerts": context["live_alerts"],
        "kpis": context["mobile_home_kpis"],
        "trends": context["home_trends"],
        "controversy_watch": context["controversy_watch"],
    })


@dashboard_bp.route("/api/creator/analytics")
def api_analytics():
    context = _build_dashboard_context()
    return jsonify({
        "cards": context["analytics_cards"],
        "views_chart": {
            "labels": context["flow_timeline_labels"],
            "values": context["flow_timeline_values"],
        },
        "controversy_chart": {
            "labels": context["chart_labels"],
            "values": context["chart_controversy"],
        },
        "creator_leaderboard": [_serialize_reel(reel) for reel in context["creator_leaderboard"]],
        "viral_probability": context["viral_probability"],
    })


@dashboard_bp.route("/api/creator/caption", methods=["GET", "POST"])
def api_create_caption():
    payload = request.get_json(silent=True) or request.values
    context = _build_dashboard_context()
    title = payload.get("title") or context["composer_defaults"]["title"]
    topic = payload.get("topic") or context["predicted_next_topic"]
    region = payload.get("region") or context["hottest_region"]
    cta = payload.get("cta") or "Drop your take below"

    return jsonify(_build_mobile_composer(topic, region, title=title, cta=cta))


@dashboard_bp.route("/api/projects", methods=["GET", "POST"])
def api_projects():
    user, error_response = _require_user_json()
    if error_response:
        return error_response

    if request.method == "GET":
        projects = ExportProject.query.filter_by(user_id=user.id).order_by(ExportProject.created_at.desc()).all()
        return jsonify({"projects": [_serialize_project(project) for project in projects]})

    payload = request.get_json(silent=True) or {}
    kind = (payload.get("kind") or "draft").strip().lower()
    status = (payload.get("status") or "saved").strip().lower()
    project_payload = {
        "title": payload.get("title") or "Untitled Project",
        "topic": payload.get("topic") or "general",
        "region": payload.get("region") or "Durban",
        "cta": payload.get("cta") or "Drop your take below",
        "caption": payload.get("caption") or "",
        "hook": payload.get("hook") or "",
        "voiceover": payload.get("voiceover") or "",
        "hashtags": payload.get("hashtags") or [],
    }
    project = _save_project(user, project_payload, kind=kind, status=status)

    return jsonify({"project": _serialize_project(project)}), 201


@dashboard_bp.route("/api/creator/schedule")
def api_schedule():
    context = _build_dashboard_context()
    return jsonify(context["schedule_plan"])


@dashboard_bp.route("/api/creator/profile")
def api_profile():
    context = _build_dashboard_context()
    return jsonify({
        "authenticated": context["profile_summary"]["authenticated"],
        "user": {
            "username": context["profile_summary"]["username"],
            "email": context["profile_summary"]["email"],
        },
        "profile": context["profile_summary"],
        "workspace": context["workspace"],
        "team_comments": context["team_comments"],
        "export_pack": context["export_pack"],
        "saved_projects": context["saved_projects"],
    })


@dashboard_bp.route("/download-pack")
def download_pack():
    reels = Reel.query.order_by(Reel.views.desc()).all()
    summary = _build_export_summary(reels)
    pdf_buffer = _build_creator_brief_pdf(summary)
    user = _current_user()

    if user:
        export_payload = {
            "title": f"{summary['predicted_next_topic']} brief",
            "topic": summary["predicted_next_topic"],
            "region": summary["hottest_region"],
            "cta": "Download and post",
            "caption": f"{summary['hottest_region']} is talking about {summary['predicted_next_topic']} right now.",
            "hook": f"Why {summary['hottest_region']} cannot ignore {summary['predicted_next_topic']} now.",
            "voiceover": f"Quick brief for {summary['hottest_region']} creators covering {summary['predicted_next_topic']}.",
            "hashtags": ["#MVPulse", f"#{summary['predicted_next_topic'].replace(' ', '')}"],
        }
        _save_project(user, export_payload, kind="export", status="downloaded")

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="mv_pulse_creator_brief.pdf",
        mimetype="application/pdf"
    )


@dashboard_bp.route("/tv")
def tv_mode():
    return dashboard()