user_preferences = {}

def update_preference(user_id, category):
    if user_id not in user_preferences:
        user_preferences[user_id] = {}

    prefs = user_preferences[user_id]
    prefs[category] = prefs.get(category, 0) + 1


def get_top_categories(user_id):
    prefs = user_preferences.get(user_id, {})
    return sorted(prefs, key=prefs.get, reverse=True)