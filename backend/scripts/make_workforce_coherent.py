"""Give the synthetic workforce a shape a real one would have.

Every field in the seeded workforce was drawn independently, so the data had no
internal structure at all:

  * department and job_title were separate random.choice calls, which put 325
    HR Analysts and 313 Sales Reps inside Engineering, and made the career-path
    ladder suggest "Senior Engineer" as the next step for an HR Business Partner
  * the same department appeared under two names: HR and Human Resources, R&D
    and Research & Development, so filters offered both and split the counts
  * tenure and rating were drawn from one distribution for everybody, so every
    department averaged 30 months and the same rating

That last one matters most. Any honest department chart over this data is flat
by construction, so the only way the product ever showed variation between
departments was by charting a column that was itself random noise. Making the
numbers honest is not enough on its own: the workforce has to have real
differences for an honest chart to find.

This pass gives each department a plausible profile, staffs it with titles that
belong to it, and merges the duplicate names. Afterwards, run
recompute_attrition_risk.py so risk reflects the corrected record.

Deterministic: same input, same output. Run with --apply to write.
"""
import argparse
import asyncio
import hashlib
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.career_ladders import LADDERS  # noqa: E402

from scripts.workforce_shape import DEPARTMENT_SHAPE, MERGE, _unit, profile_for

# The shape lives in scripts/workforce_shape.py, shared with the initial seed so
# a fresh install cannot reintroduce what this pass exists to correct.
DEPARTMENTS = DEPARTMENT_SHAPE


async def main(apply: bool) -> int:
    conn = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        user=os.getenv("POSTGRES_USER", "hiro_user"),
        password=os.getenv("POSTGRES_PASSWORD", "hiro_password_production"),
        database=os.getenv("POSTGRES_DB", "hiro_db"),
    )
    try:
        rows = await conn.fetch("SELECT employee_uuid, department FROM employee_pii")
        print(f"{len(rows)} employees on file.")

        updates, misplaced = [], 0
        for row in rows:
            department = MERGE.get(row["department"], row["department"])
            if department not in DEPARTMENTS:
                # Anything unrecognised is spread across the real departments
                # rather than left in a department of one.
                names = sorted(DEPARTMENTS)
                department = names[int(_unit(row["employee_uuid"], "dept") * len(names))]
                misplaced += 1
            title, tenure, rating = profile_for(row["employee_uuid"], department)
            updates.append((row["employee_uuid"], department, title, tenure, rating))

        print(f"{misplaced} employee(s) sat in a department that is not part of the org.")
        if not apply:
            print("\nSample of what would change:")
            for u in updates[:5]:
                print(f"  {u[0]:22s} -> {u[1]:24s} {u[2]:28s} tenure {u[3]:3d}  rating {u[4]}")
            print("\nNothing was written. Re-run with --apply.")
            return 0

        async with conn.transaction():
            await conn.executemany(
                """UPDATE employee_pii
                   SET department = $2, job_title = $3, tenure_months = $4,
                       hire_date = (CURRENT_DATE - make_interval(months => $4))::date
                   WHERE employee_uuid = $1""",
                [(u[0], u[1], u[2], u[3]) for u in updates],
            )
            # Performance reviews have to agree with the profile, or the rating
            # the risk model reads contradicts the one the workforce has.
            await conn.executemany(
                """UPDATE performance_reviews SET overall_rating = $2
                   WHERE employee_uuid = $1""",
                [(u[0], u[4]) for u in updates],
            )

        print(f"\nUpdated {len(updates)} employees.\n")
        for row in await conn.fetch(
            """SELECT e.department, COUNT(*) n, ROUND(AVG(e.tenure_months), 1) tenure,
                      ROUND(AVG(p.overall_rating), 2) rating
               FROM employee_pii e
               LEFT JOIN performance_reviews p ON p.employee_uuid = e.employee_uuid
               GROUP BY e.department ORDER BY n DESC"""
        ):
            print(f"  {row['department']:24s} n={row['n']:6d}  avg tenure {row['tenure']:6}  avg rating {row['rating']}")
        print("\nNow run recompute_attrition_risk.py --apply so risk follows the record.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the corrected workforce")
    sys.exit(asyncio.run(main(parser.parse_args().apply)))
