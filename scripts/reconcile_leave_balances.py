"""Bring leave balances in line with the leave that was actually approved.

Approving leave never drew the entitlement down, so used_hours sat at zero for
every employee however much leave had been granted. Now that approval moves the
balance, the stored figures have to be reconciled once or they stay wrong for
anyone with history.

For each employee: used_hours becomes the total approved, and the remaining
balance is reduced by the same amount, floored at zero. Anyone left on zero can
be granted a fresh entitlement through HR (POST /api/hr/leave/balance/{id}).

Safe to run more than once: it recomputes from the requests each time rather
than applying a delta. Run with --apply to write; without it, it only reports.
"""
import argparse
import asyncio
import os
import sys

import asyncpg


async def main(apply: bool) -> int:
    conn = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        user=os.getenv("POSTGRES_USER", "hiro_user"),
        password=os.getenv("POSTGRES_PASSWORD", "hiro_password_production"),
        database=os.getenv("POSTGRES_DB", "hiro_db"),
    )
    try:
        rows = await conn.fetch(
            """SELECT lb.employee_uuid,
                      lb.balance_hours,
                      lb.used_hours,
                      COALESCE(a.taken, 0) AS taken
               FROM leave_balance lb
               LEFT JOIN (SELECT employee_uuid, SUM(hours) AS taken
                          FROM leave_requests WHERE status = 'APPROVED'
                          GROUP BY employee_uuid) a
                 ON a.employee_uuid = lb.employee_uuid
               WHERE COALESCE(a.taken, 0) <> COALESCE(lb.used_hours, 0)"""
        )

        if not rows:
            print("Every leave balance already matches the leave that was approved.")
            return 0

        print(f"{len(rows)} balance(s) do not match the approved leave behind them:\n")
        for r in rows:
            entitlement = float(r["balance_hours"]) + float(r["used_hours"] or 0)
            taken = float(r["taken"])
            remaining = max(entitlement - taken, 0.0)
            print(f"  {r['employee_uuid']}: taken {taken:g}h against an entitlement of "
                  f"{entitlement:g}h, leaving {remaining:g}h "
                  f"(stored: {float(r['balance_hours']):g}h left, {float(r['used_hours'] or 0):g}h used)")

        if not apply:
            print("\nNothing was written. Re-run with --apply to correct these.")
            return 0

        async with conn.transaction():
            await conn.execute(
                """UPDATE leave_balance lb
                   SET used_hours = a.taken,
                       balance_hours = GREATEST(
                           lb.balance_hours + COALESCE(lb.used_hours, 0) - a.taken, 0)
                   FROM (SELECT employee_uuid, SUM(hours) AS taken
                         FROM leave_requests WHERE status = 'APPROVED'
                         GROUP BY employee_uuid) a
                   WHERE a.employee_uuid = lb.employee_uuid
                     AND COALESCE(lb.used_hours, 0) <> a.taken"""
            )
        print(f"\nCorrected {len(rows)} balance(s).")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the corrections")
    sys.exit(asyncio.run(main(parser.parse_args().apply)))
