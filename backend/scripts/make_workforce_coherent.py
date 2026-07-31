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

# Departments the duplicates fold into.
MERGE = {
    "HR": "Human Resources",
    "R&D": "Research & Development",
}

# Each department: the ladder that staffs it, and the shape of its workforce.
#
# tenure_centre / tenure_spread are in months; rating_centre is out of 5. The
# figures are ordinary industry shapes: sales turns over fastest, legal and
# finance keep people longest, support sits in between on both.
DEPARTMENTS = {
    "Engineering": {
        "titles": ["Graduate Engineer", "Engineer", "Senior Engineer", "Staff Engineer",
                   "Principal Engineer", "Engineering Manager", "Director of Engineering", "VP Engineering"],
        "weights": [10, 26, 24, 14, 8, 12, 4, 2],
        "tenure_centre": 34, "tenure_spread": 22, "rating_centre": 3.85,
    },
    "Research & Development": {
        "titles": ["Research Assistant", "Research Scientist", "Senior Research Scientist",
                   "Principal Scientist", "Research Lead", "Director of Research"],
        "weights": [12, 30, 26, 14, 12, 6],
        "tenure_centre": 46, "tenure_spread": 26, "rating_centre": 3.95,
    },
    "Sales": {
        "titles": ["Sales Development Rep", "Sales Associate", "Account Executive",
                   "Senior Account Executive", "Sales Manager", "Regional Sales Director", "VP Sales"],
        "weights": [18, 22, 24, 14, 12, 7, 3],
        "tenure_centre": 19, "tenure_spread": 14, "rating_centre": 3.55,
    },
    "Marketing": {
        "titles": ["Marketing Assistant", "Marketing Specialist", "Content Strategist",
                   "Brand Manager", "Product Marketing Manager", "Marketing Director"],
        "weights": [14, 28, 18, 18, 14, 8],
        "tenure_centre": 27, "tenure_spread": 18, "rating_centre": 3.70,
    },
    "Finance": {
        "titles": ["Finance Analyst", "Senior Finance Analyst", "Financial Controller",
                   "Finance Business Partner", "Finance Manager", "Head of Finance", "CFO"],
        "weights": [20, 24, 18, 16, 14, 6, 2],
        "tenure_centre": 52, "tenure_spread": 26, "rating_centre": 3.80,
    },
    "Legal": {
        "titles": ["Paralegal", "Legal Counsel", "Senior Legal Counsel",
                   "Compliance Officer", "Head of Legal", "General Counsel"],
        "weights": [18, 30, 22, 18, 8, 4],
        "tenure_centre": 58, "tenure_spread": 28, "rating_centre": 3.90,
    },
    "Operations": {
        "titles": ["Operations Assistant", "Operations Analyst", "Operations Specialist",
                   "Operations Manager", "Head of Operations", "COO"],
        "weights": [16, 26, 24, 22, 9, 3],
        "tenure_centre": 33, "tenure_spread": 20, "rating_centre": 3.65,
    },
    "Human Resources": {
        "titles": ["HR Assistant", "HR Analyst", "HR Business Partner", "Talent Acquisition Partner",
                   "Compensation Analyst", "HR Manager", "Head of People", "CHRO"],
        "weights": [14, 22, 20, 14, 12, 12, 4, 2],
        "tenure_centre": 40, "tenure_spread": 22, "rating_centre": 3.75,
    },
    "IT": {
        "titles": ["IT Support Analyst", "Systems Administrator", "Network Engineer",
                   "IT Security Analyst", "IT Manager", "Head of IT"],
        "weights": [24, 22, 18, 16, 14, 6],
        "tenure_centre": 36, "tenure_spread": 20, "rating_centre": 3.60,
    },
    "Support": {
        "titles": ["Support Agent", "Senior Support Agent", "Support Team Lead",
                   "Customer Success Manager", "Head of Support"],
        "weights": [34, 26, 18, 16, 6],
        "tenure_centre": 16, "tenure_spread": 12, "rating_centre": 3.50,
    },
    "HRIT": {
        "titles": ["HRIS Analyst", "HRIS Specialist", "HR Systems Engineer",
                   "HRIT Manager", "Head of HR Technology"],
        "weights": [26, 24, 22, 20, 8],
        "tenure_centre": 41, "tenure_spread": 22, "rating_centre": 3.80,
    },
    "Executive": {
        "titles": ["Chief of Staff", "VP Strategy", "Chief Operating Officer",
                   "Chief Financial Officer", "Chief Executive Officer"],
        "weights": [34, 30, 18, 12, 6],
        "tenure_centre": 74, "tenure_spread": 30, "rating_centre": 4.10,
    },
}


def _unit(seed: str, salt: str) -> float:
    """A stable number in [0,1) for this employee and purpose.

    Derived from the employee id so the pass is deterministic: the same input
    always produces the same workforce, however many times it is run.
    """
    digest = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def _bell(seed: str, salt: str) -> float:
    """Roughly normal in [0,1), centred on 0.5. Three draws is close enough."""
    return sum(_unit(seed, f"{salt}{i}") for i in range(3)) / 3.0


def _pick(seed: str, titles, weights) -> str:
    total = sum(weights)
    point = _unit(seed, "title") * total
    running = 0.0
    for title, weight in zip(titles, weights):
        running += weight
        if point < running:
            return title
    return titles[-1]


def profile_for(employee_uuid: str, department: str):
    """The title, tenure and rating this person should have."""
    spec = DEPARTMENTS[department]
    title = _pick(employee_uuid, spec["titles"], spec["weights"])

    # Seniority pulls tenure up: a principal has been here longer than a graduate.
    rank = spec["titles"].index(title) / max(1, len(spec["titles"]) - 1)
    centre = spec["tenure_centre"] * (0.55 + 0.9 * rank)
    tenure = centre + (_bell(employee_uuid, "tenure") - 0.5) * 2 * spec["tenure_spread"]
    tenure = int(max(1, min(240, round(tenure))))

    rating = spec["rating_centre"] + (_bell(employee_uuid, "rating") - 0.5) * 2.0
    rating = round(max(1.0, min(5.0, rating)), 2)
    return title, tenure, rating


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
