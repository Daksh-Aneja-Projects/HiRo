"""Real, persistent data layer for the Collaboration Hub (social feed + recognition).

Backed by MongoDB (same store the users live in, so recognition can resolve real
display names). Functions take a motor `db` handle so they're unit-testable with a
fake. Field shapes match exactly what pages/SocialFeed.js renders.
"""
import uuid
from datetime import datetime, timezone, timedelta

FEED_LIMIT = 50
LEADERBOARD_LIMIT = 20
MAX_POST_LEN = 2000
MAX_REASON_LEN = 500


def get_db(request):
    from config.settings import settings
    return request.app.state.mongo_client[settings.MONGO_DB_NAME]


async def list_feed(db, limit: int = FEED_LIMIT):
    """Recent posts, newest first. Shape: id, user_name, timestamp, content, upvotes, downvotes."""
    return await db.social_posts.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)


async def create_post(db, *, user_id, user_name, content):
    content = (content or "").strip()
    if not content:
        raise ValueError("Post content cannot be empty.")
    post = {
        "id": f"POST-{uuid.uuid4().hex[:12]}",
        "user_id": user_id or "unknown",
        "user_name": user_name or "Anonymous",
        "content": content[:MAX_POST_LEN],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "upvotes": 0,
        "downvotes": 0,
    }
    await db.social_posts.insert_one(dict(post))  # insert_one mutates its arg (adds _id)
    return post


async def leaderboard(db, limit: int = LEADERBOARD_LIMIT):
    """Star counts per recipient, most-starred first. Shape: user_id, user_name, stars."""
    rows = await db.recognition_stars.aggregate([
        {"$group": {"_id": "$to_user", "stars": {"$sum": 1}, "user_name": {"$last": "$to_user_name"}}},
        {"$sort": {"stars": -1}},
        {"$limit": limit},
    ]).to_list(limit)
    return [{"user_id": r["_id"], "user_name": r.get("user_name") or r["_id"], "stars": r["stars"]} for r in rows]


async def give_star(db, *, from_user, to_user, reason):
    """Award a recognition star.

    `to_user` may be a sign-in name or a Postgres employee id: the manager's
    roster keys people by employee id, so requiring a username forced the UI to
    make an extra lookup call per star.
    """
    if not to_user:
        raise ValueError("Choose someone to recognise.")

    target = await db.users.find_one({"username": to_user}) \
        or await db.users.find_one({"employee_uuid": to_user})
    if not target:
        raise ValueError(f"No account matches '{to_user}'.")

    # Normalise to the sign-in name so the leaderboard groups correctly however
    # the caller identified the person.
    to_user = target.get("username") or to_user
    if to_user == from_user:
        raise ValueError("You cannot give recognition to yourself.")
    to_user_name = target.get("full_name") or to_user
    await db.recognition_stars.insert_one({
        "from_user": from_user,
        "to_user": to_user,
        "to_user_name": to_user_name,
        "reason": (reason or "").strip()[:MAX_REASON_LEN],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "Star Given", "to_user": to_user, "to_user_name": to_user_name, "from_user": from_user}


async def seed(db, employees):
    """Seed a handful of real-looking posts + a star distribution across the demo users,
    so the feed and leaderboard show live, non-empty data on a fresh boot. Idempotent."""
    await db.social_posts.delete_many({})
    await db.recognition_stars.delete_many({})

    by_name = [(e["username"], e.get("name") or e["username"]) for e in employees]
    now = datetime.now(timezone.utc)

    messages = [
        "Shipped the Q3 workforce-planning dashboard ahead of schedule. Huge thanks to the team!",
        "Reminder: benefits open-enrollment closes Friday. Reach out to HRBP with questions.",
        "Welcome to our newest joiners this week. Say hi when you get a chance!",
        "The digital-twin attrition model just flagged three retention wins. Great collaboration.",
        "Kudos to Support for clearing the ticket backlog two days early.",
    ]
    posts = []
    for i, msg in enumerate(messages):
        uname, name = by_name[i % len(by_name)]
        posts.append({
            "id": f"POST-SEED-{i:03d}",
            "user_id": uname,
            "user_name": name,
            "content": msg,
            "timestamp": (now - timedelta(hours=i * 5 + 1)).isoformat(),
            "upvotes": (i * 3) % 7,
            "downvotes": i % 2,
            # Flagged so the UI can label it. Without this, seeded content is
            # indistinguishable from real activity to anyone reading the feed.
            "is_sample": True,
        })
    await db.social_posts.insert_many(posts)

    # A star distribution so the leaderboard is ranked and non-trivial.
    star_counts = [5, 4, 3, 3, 2, 2, 1, 1]
    stars = []
    for idx, count in enumerate(star_counts):
        if idx >= len(by_name):
            break
        to_user, to_name = by_name[idx]
        for j in range(count):
            giver = by_name[(idx + j + 1) % len(by_name)][0]
            stars.append({
                "from_user": giver,
                "to_user": to_user,
                "to_user_name": to_name,
                "reason": "Recognized for outstanding contribution.",
                "created_at": (now - timedelta(days=idx, hours=j)).isoformat(),
            })
    await db.recognition_stars.insert_many(stars)
    return len(posts), len(stars)
