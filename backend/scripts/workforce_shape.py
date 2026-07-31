"""The shape a synthetic workforce should have.

One definition, used by the initial seed and by the repair pass that corrects an
existing database. Without it the two drift, and a fresh install reintroduces
exactly what the repair removed.

Every field used to be drawn independently: department, job title, tenure,
rating and attrition risk were five unrelated random values. That put HR
Analysts inside Engineering, gave every department the same average tenure, and
left an attrition column that was pure noise while driving the risk chart, the
retention figure and the explanation panel's strongest factor.

Here, a person's record hangs together. Seniority and length of service move
together, each department has its own turnover and rating profile, and risk is
derived from the record rather than drawn.
"""
import hashlib
from typing import Dict, List, Tuple

from services.career_ladders import LADDERS

# How each department is shaped. Ordinary industry patterns: sales turns over
# fastest, legal and finance hold people longest, support sits between the two.
#
# weights   how the department is distributed across its ladder, junior first
# tenure_*  months
# rating_*  out of 5
DEPARTMENT_SHAPE: Dict[str, Dict] = {
    "Engineering":            {"weights": [10, 26, 24, 14, 8, 12, 4, 2], "tenure_centre": 34, "tenure_spread": 22, "rating_centre": 3.85},
    "Research & Development": {"weights": [12, 30, 26, 14, 12, 6],       "tenure_centre": 46, "tenure_spread": 26, "rating_centre": 3.95},
    "Sales":                  {"weights": [18, 22, 24, 14, 12, 7, 3],    "tenure_centre": 19, "tenure_spread": 14, "rating_centre": 3.55},
    "Marketing":              {"weights": [14, 28, 18, 18, 14, 8],       "tenure_centre": 27, "tenure_spread": 18, "rating_centre": 3.70},
    "Finance":                {"weights": [20, 24, 18, 16, 14, 6, 2],    "tenure_centre": 52, "tenure_spread": 26, "rating_centre": 3.80},
    "Legal":                  {"weights": [18, 30, 22, 18, 8, 4],        "tenure_centre": 58, "tenure_spread": 28, "rating_centre": 3.90},
    "Operations":             {"weights": [16, 26, 24, 22, 9, 3],        "tenure_centre": 33, "tenure_spread": 20, "rating_centre": 3.65},
    "Human Resources":        {"weights": [14, 22, 20, 14, 12, 12, 4, 2],"tenure_centre": 40, "tenure_spread": 22, "rating_centre": 3.75},
    "IT":                     {"weights": [24, 22, 18, 16, 14, 6],       "tenure_centre": 36, "tenure_spread": 20, "rating_centre": 3.60},
    "Support":                {"weights": [34, 26, 18, 16, 6],           "tenure_centre": 16, "tenure_spread": 12, "rating_centre": 3.50},
    "HRIT":                   {"weights": [26, 24, 22, 20, 8],           "tenure_centre": 41, "tenure_spread": 22, "rating_centre": 3.80},
    "Executive":              {"weights": [34, 30, 18, 12, 6],           "tenure_centre": 74, "tenure_spread": 30, "rating_centre": 4.10},
}

# Departments that used to appear under two names, splitting their own counts
# and offering both to every filter control.
MERGE = {"HR": "Human Resources", "R&D": "Research & Development"}


def _unit(seed: str, salt: str) -> float:
    """A stable number in [0,1) for this person and purpose.

    Derived from the employee id, so seeding and repairing produce the same
    workforce however many times either runs.
    """
    digest = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def _bell(seed: str, salt: str) -> float:
    """Roughly normal in [0,1), centred on 0.5."""
    return sum(_unit(seed, f"{salt}{i}") for i in range(3)) / 3.0


def _pick(seed: str, titles: List[str], weights: List[int]) -> str:
    point = _unit(seed, "title") * sum(weights)
    running = 0.0
    for title, weight in zip(titles, weights):
        running += weight
        if point < running:
            return title
    return titles[-1]


def profile_for(employee_uuid: str, department: str) -> Tuple[str, int, float]:
    """The job title, tenure in months and rating this person should have."""
    shape = DEPARTMENT_SHAPE[department]
    titles = LADDERS[department]
    title = _pick(employee_uuid, titles, shape["weights"])

    # Seniority pulls tenure up: a principal has been here longer than a graduate.
    rank = titles.index(title) / max(1, len(titles) - 1)
    centre = shape["tenure_centre"] * (0.55 + 0.9 * rank)
    tenure = centre + (_bell(employee_uuid, "tenure") - 0.5) * 2 * shape["tenure_spread"]
    tenure = int(max(1, min(240, round(tenure))))

    rating = shape["rating_centre"] + (_bell(employee_uuid, "rating") - 0.5) * 2.0
    return title, tenure, round(max(1.0, min(5.0, rating)), 2)


def risk_for(tenure_months: int, rating: float) -> float:
    """Attrition risk derived from the record.

    The same shape as scripts/recompute_attrition_risk.py, which recomputes this
    across an existing workforce. Risk builds through the first three years and
    falls after five; weak performers are at risk of leaving, and so are the
    very strongest, who have the most options elsewhere.
    """
    risk = 0.40

    if tenure_months < 6:
        risk -= 0.06
    elif tenure_months < 12:
        risk += 0.04
    elif tenure_months <= 36:
        risk += 0.14 * (1 - (tenure_months - 12) / 24.0)
    elif tenure_months <= 60:
        risk -= 0.03
    else:
        risk -= 0.09

    if rating < 2.5:
        risk += 0.18
    elif rating < 3.2:
        risk += 0.08
    elif rating > 4.6:
        risk += 0.11
    elif rating > 4.2:
        risk += 0.04
    else:
        risk -= 0.06

    # No pay history on a freshly seeded record.
    risk += 0.03
    return round(max(0.05, min(0.95, risk)), 2)
