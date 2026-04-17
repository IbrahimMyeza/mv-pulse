from models.voice_reply import VoiceReply


def suggest_clips_for_video(video, insights_by_reply_id=None, limit=3):
    if not video:
        return []

    suggestions = []
    replies = VoiceReply.query.filter_by(video_id=video.id).order_by(VoiceReply.created_at.desc()).limit(12).all()
    insights_by_reply_id = insights_by_reply_id or {}

    for reply in replies:
        insight = insights_by_reply_id.get(reply.id) or getattr(reply, "insight_record", None)
        transcript = (reply.transcript or "").strip()
        if not transcript:
            continue
        energy = getattr(insight, "energy_score", 0.0) if insight else 0.0
        intelligence = getattr(insight, "intelligence_score", 0.0) if insight else 0.0
        emphasis = 0.15 if any(marker in transcript.lower() for marker in ["listen", "wait", "exactly", "truth", "viral", "important"]) else 0.0
        clip_score = round(energy + intelligence + emphasis, 2)
        if clip_score < 0.45:
            continue

        start_second = 0
        duration = max(min(int(reply.duration or 0) or 12, 30), 8)
        suggestions.append({
            "reply_id": reply.id,
            "video_id": video.id,
            "start_second": start_second,
            "end_second": start_second + duration,
            "score": clip_score,
            "headline": "This moment is going viral",
            "reason": transcript[:96] + ("..." if len(transcript) > 96 else ""),
            "target_url": f"/video/{video.id}?focus_reply_id={reply.id}#reply-{reply.id}",
        })

    suggestions.sort(key=lambda item: item["score"], reverse=True)
    return suggestions[:limit]
