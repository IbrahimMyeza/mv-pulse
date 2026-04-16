creator_scores = {}

def update_creator_score(creator_id, engagement_score):
    if creator_id not in creator_scores:
        creator_scores[creator_id] = 100

    creator_scores[creator_id] += engagement_score * 0.1
    return creator_scores[creator_id]


def get_creator_score(creator_id):
    return creator_scores.get(creator_id, 100)