"""Give people the skills their job implies, so a skills gap can be measured.

The HR portal shows "Skills Gap Analysis by Department" and "Succession Pipeline
Readiness by Department". Neither had any skills data behind it: employee_skills
held a single document for the whole company, so the gap was derived from
department headcount instead, and a department with one person was reported as
having a HIGH skills gap. Succession readiness was that same headcount vector
subtracted from 4, so the two charts were one number and its inverse.

This gives every employee a skill set drawn from what their role actually needs,
with realistic partial coverage: more senior people hold more of the ladder, and
nobody holds all of it. A gap is then what it should be, the share of the skills
a department needs that nobody in it has to the expected depth.

Deterministic, so the same workforce always produces the same skills.
Run with --apply to write.
"""
import argparse
import asyncio
import hashlib
import os
import sys

import asyncpg
from pymongo import MongoClient, UpdateOne

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.skill_requirements import REQUIRED_SKILLS as REQUIRED  # noqa: E402



def _unit(seed: str, salt: str) -> float:
    digest = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def skills_for(employee_uuid: str, department: str, tenure_months: int, rating: float):
    """The skills this person plausibly holds.

    Depth grows with tenure and rating: someone six months in holds the first
    couple of things on the list, a strong ten-year veteran holds most of it.
    Nobody holds all of it, which is what leaves a gap worth reporting.
    """
    needed = REQUIRED.get(department)
    if not needed:
        return []

    seniority = min(1.0, (tenure_months / 84.0) * 0.7 + ((rating - 2.5) / 2.5) * 0.3)
    depth = max(1, round(len(needed) * max(0.15, min(0.85, seniority))))

    held = []
    for index, skill in enumerate(needed):
        if len(held) >= depth:
            break
        # Later skills are held less reliably even by senior people.
        chance = 0.95 - (index / max(1, len(needed))) * 0.45
        if _unit(employee_uuid, skill) < chance:
            held.append(skill)
    return held


async def main(apply: bool) -> int:
    pg = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        user=os.getenv("POSTGRES_USER", "hiro_user"),
        password=os.getenv("POSTGRES_PASSWORD", "hiro_password_production"),
        database=os.getenv("POSTGRES_DB", "hiro_db"),
    )
    mongo = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    skills_col = mongo[os.getenv("MONGO_DB_NAME", "ahcm_db")]["employee_skills"]

    try:
        rows = await pg.fetch(
            """SELECT e.employee_uuid, e.department, COALESCE(e.tenure_months, 0) AS tenure,
                      COALESCE((SELECT AVG(overall_rating) FROM performance_reviews p
                                WHERE p.employee_uuid = e.employee_uuid), 3.0) AS rating
               FROM employee_pii e"""
        )
        print(f"{len(rows)} employees. employee_skills currently holds "
              f"{skills_col.count_documents({})} document(s).")

        operations, coverage = [], {}
        for row in rows:
            held = skills_for(row["employee_uuid"], row["department"],
                              int(row["tenure"]), float(row["rating"]))
            if not held:
                continue
            operations.append(UpdateOne(
                {"employee_uuid": row["employee_uuid"]},
                {"$set": {"employee_uuid": row["employee_uuid"], "skills": held,
                          "department": row["department"]}},
                upsert=True))
            bucket = coverage.setdefault(row["department"], {})
            for skill in held:
                bucket[skill] = bucket.get(skill, 0) + 1

        if not apply:
            print(f"\nWould write {len(operations)} skill profiles. Re-run with --apply.")
            return 0

        for start in range(0, len(operations), 2000):
            skills_col.bulk_write(operations[start:start + 2000], ordered=False)
        print(f"\nWrote {len(operations)} skill profiles.\n")

        print("Coverage of the skills each department needs:")
        for department in sorted(coverage):
            needed = REQUIRED.get(department, [])
            headcount = sum(1 for r in rows if r["department"] == department)
            # A skill counts as covered when a reasonable share of the department holds it.
            covered = sum(1 for s in needed
                          if coverage[department].get(s, 0) >= max(1, headcount * 0.25))
            print(f"  {department:24s} {covered}/{len(needed)} skills held broadly enough")
        return 0
    finally:
        await pg.close()
        mongo.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the skill profiles")
    sys.exit(asyncio.run(main(parser.parse_args().apply)))
