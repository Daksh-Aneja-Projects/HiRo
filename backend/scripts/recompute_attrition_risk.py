"""Recompute attrition risk from the workforce record instead of a random draw.

employee_pii.dtla_risk_score was seeded with random.uniform(0.10, 0.99) and
nothing ever recomputed it. That column is the sole input to the overall risk
score, to "Attrition Risk by Department", to "Projected retention", and to the
factor the explanation panel names as the strongest driver.

Because a uniform draw averages to 0.545 whatever the sample, every department
with a meaningful headcount converged to 54.5% by construction: individual
variance was 26 points, yet no department sat more than 4 points from the mean.
The chart could not respond to anything about the workforce, and it never did.

This replaces the column with a value derived from signals that are really on
file, so the aggregates move when the workforce does:

  tenure       risk climbs through the first three years and falls after five
  performance  low ratings raise it; the strongest performers raise it too,
               because they are the most marketable
  pay history  a long time since the last change raises it
  standing     rating relative to the rest of that department

It is a heuristic, not a trained model, and everything that surfaces it says so.
Run with --apply to write; without it, this only reports what would change.
"""
import argparse
import asyncio
import os
import sys

import asyncpg

# Expressed in SQL so it runs set-based over the whole workforce in one pass.
RISK_SQL = """
WITH facts AS (
    SELECT e.employee_uuid,
           COALESCE(e.tenure_months, 0)                      AS tenure,
           r.avg_rating,
           d.dept_avg_rating,
           c.last_raise_months
    FROM employee_pii e
    LEFT JOIN LATERAL (
        SELECT AVG(overall_rating) AS avg_rating
        FROM performance_reviews p WHERE p.employee_uuid = e.employee_uuid
    ) r ON TRUE
    LEFT JOIN LATERAL (
        SELECT AVG(p2.overall_rating) AS dept_avg_rating
        FROM employee_pii e2
        JOIN performance_reviews p2 ON p2.employee_uuid = e2.employee_uuid
        WHERE e2.department = e.department
    ) d ON TRUE
    LEFT JOIN LATERAL (
        SELECT EXTRACT(EPOCH FROM (NOW() - MAX(ch.effective_date)::timestamptz)) / 2629746.0
                   AS last_raise_months
        FROM comp_history ch WHERE ch.employee_uuid = e.employee_uuid
    ) c ON TRUE
),
scored AS (
    SELECT employee_uuid,
           GREATEST(0.05, LEAST(0.95,
               0.40
               -- Settling in: risk builds over the first three years, then eases.
               + CASE
                     WHEN tenure < 6   THEN -0.06
                     WHEN tenure < 12  THEN  0.04
                     WHEN tenure <= 36 THEN  0.14 * (1 - (tenure - 12) / 24.0)
                     WHEN tenure <= 60 THEN -0.03
                     ELSE                   -0.09
                 END
               -- Weak performers are at risk of leaving; so are the very
               -- strongest, who have the most options elsewhere.
               + CASE
                     WHEN avg_rating IS NULL   THEN  0.00
                     WHEN avg_rating < 2.5     THEN  0.18
                     WHEN avg_rating < 3.2     THEN  0.08
                     WHEN avg_rating > 4.6     THEN  0.11
                     WHEN avg_rating > 4.2     THEN  0.04
                     ELSE                           -0.06
                 END
               -- Standing within their own department.
               + CASE
                     WHEN avg_rating IS NULL OR dept_avg_rating IS NULL THEN 0.00
                     ELSE LEAST(0.08, GREATEST(-0.08,
                              (dept_avg_rating - avg_rating) * 0.10))
                 END
               -- Nothing on the pay record for a long time.
               + CASE
                     WHEN last_raise_months IS NULL     THEN  0.03
                     WHEN last_raise_months > 24        THEN  LEAST(0.12,
                              0.10 * (last_raise_months - 24) / 12.0)
                     WHEN last_raise_months < 6         THEN -0.05
                     ELSE                                     0.00
                 END
           )) AS risk
    FROM facts
)
UPDATE employee_pii e
SET dtla_risk_score = ROUND(s.risk::numeric, 2)
FROM scored s
WHERE s.employee_uuid = e.employee_uuid
"""

SPREAD_SQL = """
SELECT department,
       COUNT(*) AS n,
       ROUND(AVG(dtla_risk_score), 3) AS avg_risk,
       ROUND(STDDEV_POP(dtla_risk_score), 3) AS sd
FROM employee_pii
GROUP BY department HAVING COUNT(*) > 25 ORDER BY avg_risk DESC
"""


async def main(apply: bool) -> int:
    conn = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        user=os.getenv("POSTGRES_USER", "hiro_user"),
        password=os.getenv("POSTGRES_PASSWORD", "hiro_password_production"),
        database=os.getenv("POSTGRES_DB", "hiro_db"),
    )
    try:
        print("Attrition risk by department, before:")
        for row in await conn.fetch(SPREAD_SQL):
            print(f"  {row['department']:28s} n={row['n']:6d}  avg={row['avg_risk']}  sd={row['sd']}")

        if not apply:
            print("\nNothing was written. Re-run with --apply to recompute.")
            return 0

        async with conn.transaction():
            result = await conn.execute(RISK_SQL)
        print(f"\n{result}\n")

        print("Attrition risk by department, after:")
        rows = await conn.fetch(SPREAD_SQL)
        for row in rows:
            print(f"  {row['department']:28s} n={row['n']:6d}  avg={row['avg_risk']}  sd={row['sd']}")

        if rows:
            spread = float(max(r["avg_risk"] for r in rows)) - float(min(r["avg_risk"] for r in rows))
            print(f"\nSpread between the highest and lowest department: {spread:.3f}")
            print("Before the recompute this was under 0.05 for any workforce, because"
                  "\nthe column was a uniform random draw.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the recomputed scores")
    sys.exit(asyncio.run(main(parser.parse_args().apply)))
