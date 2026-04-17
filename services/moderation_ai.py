from collections import Counter

FLAGGED_TERMS = {
    "hate": 0.28,
    "idiot": 0.18,
    "stupid": 0.18,
    "trash": 0.14,
    "kill": 0.4,
    "attack": 0.24,
    "shut up": 0.18,
    "worthless": 0.22,
    "violent": 0.26,
    "harass": 0.26,
}


def moderation_assessment(text):
    content = (text or "").lower()
    if not content:
        return {
            "toxicity_score": 0.0,
            "moderation_state": "clear",
            "matched_terms": [],
            "soft_warning": None,
        }

    matches = []
    score = 0.0
    for term, weight in FLAGGED_TERMS.items():
        occurrences = content.count(term)
        if occurrences:
            matches.extend([term] * occurrences)
            score += weight * occurrences

    uppercase_tokens = [token for token in (text or "").split() if token.isupper() and len(token) > 3]
    exclamation_boost = min((text or "").count("!"), 4) * 0.04
    score += min(len(uppercase_tokens), 3) * 0.05 + exclamation_boost
    score = round(min(score, 1.0), 2)

    if score >= 0.72:
        state = "review"
        warning = "This reply may be flagged for review."
    elif score >= 0.45:
        state = "downrank"
        warning = "This reply may be downranked for aggressive language."
    elif score >= 0.2:
        state = "warn"
        warning = "This reply contains heated language."
    else:
        state = "clear"
        warning = None

    return {
        "toxicity_score": score,
        "moderation_state": state,
        "matched_terms": [term for term, _ in Counter(matches).most_common(5)],
        "soft_warning": warning,
    }
