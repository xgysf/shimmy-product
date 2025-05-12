import os
import pickle
import random
from datetime import datetime, timedelta
from types import SimpleNamespace

DUMMY_DATA_FILE = "dummy_data.pkl"
FAKE_USERS = None

def generate_dummy_data(n_records=10000, n_users=500):
    pages = ["Home", "Explore", "Post", "My Network", "Notifications", "Profile", "Settings", "About", "Contact"]
    sources = ["Google", "Direct", "Facebook", "Twitter", "LinkedIn", "Other"]
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Mozilla/5.0 (Linux; Android 10)",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
    ]
    feedbacks = ["", "Great site!", "Needs improvement", "I love it", "Not satisfied", ""]
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=60)
    
    # Generate a fixed pool of user IDs and assign each a fake first_login.
    user_ids = [str(i) for i in range(1, n_users+1)]
    fake_users = {}
    user_first_logins = {}
    total_seconds = int((end_date - start_date).total_seconds())
    for uid in user_ids:
        random_seconds = random.randint(0, total_seconds)
        first_login = start_date + timedelta(seconds=random_seconds)
        user_first_logins[uid] = first_login
        fake_users[uid] = SimpleNamespace(user_id=uid, first_login=first_login)
    
    sessions = []
    for _ in range(n_records):
        user_id = random.choice(user_ids)
        user_first = user_first_logins[user_id]
        delta_seconds = int((end_date - user_first).total_seconds())
        if delta_seconds > 0:
            session_seconds = random.randint(0, delta_seconds)
            visit_time = user_first + timedelta(seconds=session_seconds)
        else:
            visit_time = user_first
        page = random.choice(pages)
        source = random.choice(sources)
        session_time = round(random.uniform(30, 600), 2)
        user_agent = random.choice(user_agents)
        feedback = random.choice(feedbacks)
        sessions.append(SimpleNamespace(
            user_id=user_id,
            timestamp=visit_time,
            page=page,
            referral_source=source,
            session_time=session_time,
            user_agent=user_agent,
            feedback=feedback
        ))
    return sessions, fake_users

def get_dummy_data(n_records=10000, n_users=500):
    """
    Loads dummy data from file if available; otherwise, generates and saves it.
    """
    global FAKE_USERS
    if os.path.exists(DUMMY_DATA_FILE):
        with open(DUMMY_DATA_FILE, "rb") as f:
            sessions, fake_users = pickle.load(f)
        FAKE_USERS = fake_users
        return sessions
    else:
        sessions, fake_users = generate_dummy_data(n_records, n_users)
        FAKE_USERS = fake_users
        with open(DUMMY_DATA_FILE, "wb") as f:
            pickle.dump((sessions, fake_users), f)
        return sessions
 