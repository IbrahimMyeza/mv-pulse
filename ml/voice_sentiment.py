POSITIVE_TERMS = {
    "agree",
    "amazing",
    "awesome",
    "beautiful",
    "best",
    "brilliant",
    "calm",
    "celebrate",
    "confident",
    "creative",
    "excellent",
    "fair",
    "good",
    "great",
    "happy",
    "helpful",
    "honest",
    "important",
    "improve",
    "inspiring",
    "interesting",
    "love",
    "powerful",
    "respect",
    "smart",
    "strong",
    "support",
    "truth",
    "useful",
    "valuable",
    "win",
}

NEGATIVE_TERMS = {
    "angry",
    "attack",
    "awful",
    "bad",
    "boring",
    "broken",
    "confused",
    "corrupt",
    "crazy",
    "dangerous",
    "disappointing",
    "disrespect",
    "fake",
    "hate",
    "horrible",
    "idiot",
    "kill",
    "liar",
    "lies",
    "mess",
    "pathetic",
    "problem",
    "sad",
    "scam",
    "stupid",
    "terrible",
    "toxic",
    "trash",
    "ugly",
    "violent",
    "wrong",
}

NEGATION_TERMS = {"no", "not", "never", "none", "hardly", "without"}


def _tokenize(text):
    cleaned = []
    for raw_token in (text or "").lower().split():
        token = raw_token.strip(".,!?;:'\"()[]{}")
        if token:
            cleaned.append(token)
    return cleaned


def analyze_voice_sentiment(text):
    tokens = _tokenize(text)
    if not tokens:
        return 0.0

    score = 0
    previous = ""
    for token in tokens:
        modifier = -1 if previous in NEGATION_TERMS else 1
        if token in POSITIVE_TERMS:
            score += 1 * modifier
        elif token in NEGATIVE_TERMS:
            score -= 1 * modifier
        previous = token

    if score == 0:
        return 0.0

    normalized = score / max(len(tokens) / 3, 1)
    return round(max(min(normalized, 1.0), -1.0), 2)