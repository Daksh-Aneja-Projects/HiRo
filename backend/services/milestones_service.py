"""Work-anniversary milestone detection + auto-recognition.

New service file (see COLLISION RULES). Calls services.social_recognition.create_post
for the actual feed post -- reusing that module's existing post-creation path rather
than writing to social_posts directly -- and tracks one post per employee per
anniversary year in Mongo milestone_posts so the same anniversary never posts twice.

HiRo has no scheduler. The org-wide "today" scan runs inside the milestones GET
handler itself, on every call -- honestly documented as check-on-view, not a
background job (see check_and_post_todays_anniversaries).
"""
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from services.postgres_client import pg_client
from services.pii_vault import PIIVault
from services import social_recognition

logger = logging.getLogger(__name__)


def _safe_replace_year(d: date, year: int) -> date:
    try:
        return d.replace(year=year)
    except ValueError:
        # Feb 29 hire date, non-leap target year.
        return d.replace(year=year, day=28)


def _nearest_anniversary(hire: date, today: date):
    """The occurrence of this hire-date (this year, last year, or next year) closest
    to today, handling the December/January wraparound. Returns (date, days_away, years)."""
    candidates = [_safe_replace_year(hire, y) for y in (today.year - 1, today.year, today.year + 1)]
    nearest = min(candidates, key=lambda a: abs((a - today).days))
    return nearest, (nearest - today).days, nearest.year - hire.year


async def _anniversaries(manager_id: Optional[str], window_days: int) -> List[Dict[str, Any]]:
    """Employees with at least one full year of service whose nearest anniversary
    falls within window_days of today. Scoped to a manager's reports, or org-wide."""
    where = "WHERE e.hire_date IS NOT NULL"
    args: List[Any] = []
    if manager_id:
        args.append(manager_id)
        where += f" AND e.manager_id = ${len(args)}"
    rows = await pg_client.fetch(
        f"SELECT e.employee_uuid, e.full_name_encrypted, e.department, e.job_title, e.hire_date "
        f"FROM employee_pii e {where}",
        *args,
    )
    today = date.today()
    vault = PIIVault.get_instance()
    out = []
    for r in rows:
        hire = r["hire_date"]
        if not hire:
            continue
        anniv, delta, years = _nearest_anniversary(hire, today)
        if years < 1 or abs(delta) > window_days:
            continue
        try:
            name = vault.decrypt(r["full_name_encrypted"]) if r.get("full_name_encrypted") else r["employee_uuid"]
        except Exception:
            logger.debug("Name decrypt failed for %s", r.get("employee_uuid"), exc_info=True)
            name = r["employee_uuid"]
        out.append({
            "employee_uuid": r["employee_uuid"], "name": name, "department": r["department"],
            "job_title": r["job_title"], "years_of_service": years,
            "anniversary_date": anniv.isoformat(), "days_away": delta,
        })
    out.sort(key=lambda x: x["days_away"])
    return out


async def check_and_post_todays_anniversaries(db) -> int:
    """Org-wide: post recognition for anyone whose anniversary is today, once per
    employee per anniversary year. Returns how many were newly posted this call."""
    today_list = await _anniversaries(manager_id=None, window_days=0)
    posted = 0
    for a in today_list:
        year_key = date.today().year
        already = await db.milestone_posts.find_one(
            {"employee_uuid": a["employee_uuid"], "anniversary_year": year_key})
        if already:
            continue
        try:
            years = a["years_of_service"]
            await social_recognition.create_post(
                db, user_id="SYSTEM", user_name="HiRo",
                content=(f"Congratulations to {a['name']} ({a['department']}) on "
                         f"{years} year{'s' if years != 1 else ''} at the company today."),
            )
            await db.milestone_posts.insert_one({
                "employee_uuid": a["employee_uuid"], "anniversary_year": year_key,
                "posted_at": datetime.now(timezone.utc).isoformat(),
            })
            posted += 1
        except Exception as e:
            logger.warning(f"Milestone post failed for {a['employee_uuid']}: {e}")
    return posted


async def milestones_for_manager(db, manager_id: str) -> Dict[str, Any]:
    posted = await check_and_post_todays_anniversaries(db)
    upcoming = [a for a in await _anniversaries(manager_id, window_days=14) if a["days_away"] >= 0]
    recent = [a for a in await _anniversaries(manager_id, window_days=7) if a["days_away"] < 0]
    return {
        "upcoming": upcoming, "recent": recent, "auto_posted_today": posted,
        "note": ("Checked on view: HiRo has no background scheduler, so today's anniversaries are "
                 "posted to the feed the next time this screen loads on the day itself."),
    }
