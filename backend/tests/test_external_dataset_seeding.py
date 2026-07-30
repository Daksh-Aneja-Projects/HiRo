"""Unit tests for real-dataset seeding (IBM HR Attrition CC0 + UCI incident log CC BY 4.0).

Uses tiny in-memory CSV fixtures (written to temp files) so the column-mapping and
sampling logic is verified without the full downloaded datasets or a live database.
"""
import asyncio
import csv
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import init_test_data as m


IBM_HEADER = [
    "Age", "Attrition", "BusinessTravel", "DailyRate", "Department", "DistanceFromHome",
    "Education", "EducationField", "EmployeeCount", "EmployeeNumber", "EnvironmentSatisfaction",
    "Gender", "HourlyRate", "JobInvolvement", "JobLevel", "JobRole", "JobSatisfaction",
    "MaritalStatus", "MonthlyIncome", "MonthlyRate", "NumCompaniesWorked", "Over18", "OverTime",
    "PercentSalaryHike", "PerformanceRating", "RelationshipSatisfaction", "StockOptionLevel",
    "TotalWorkingYears", "TrainingTimesLastYear", "WorkLifeBalance", "YearsAtCompany",
    "YearsInCurrentRole", "YearsSinceLastPromotion", "YearsWithCurrManager",
]


class FakePgClient:
    def __init__(self):
        self.executemany_calls = []

    async def executemany_async(self, query, args_list, **kwargs):
        self.executemany_calls.append((query, args_list))

    def transaction(self, *a, **kw):
        class _T:
            async def __aenter__(self_): return self_
            async def __aexit__(self_, *a): return False
        return _T()


class FakePQC:
    def encrypt(self, plaintext, data_context="default", **kw):
        return f"ENC({plaintext})", {}


def _write_ibm_csv(rows):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8-sig")
    w = csv.DictWriter(f, fieldnames=IBM_HEADER)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    f.close()
    return Path(f.name)


def test_ibm_hr_seed_maps_and_inserts(monkeypatch):
    row = {h: "1" for h in IBM_HEADER}
    row.update({
        "EmployeeNumber": "42", "Department": "Sales", "JobRole": "Sales Rep",
        "Attrition": "Yes", "JobSatisfaction": "2", "MonthlyIncome": "5000",
        "YearsAtCompany": "3", "PerformanceRating": "3", "PercentSalaryHike": "12",
    })
    path = _write_ibm_csv([row])
    monkeypatch.setattr(m, "IBM_HR_CSV", path)
    fake = FakePgClient()
    monkeypatch.setattr(m, "pg_client", fake)

    asyncio.run(m.seed_ibm_hr_dataset(FakePQC()))

    pii_call = fake.executemany_calls[0]
    assert "employee_pii" in pii_call[0]
    pii_row = pii_call[1][0]
    assert pii_row[0] == "IBM-42"           # employee_uuid = IBM-{EmployeeNumber}
    assert pii_row[9] == "Sales"            # department
    assert pii_row[13] == 36                # tenure_months = 3 years * 12
    # attrition=Yes, job_satisfaction=2 -> risk = 0.65 + (1-0.5)*0.25 = 0.775
    assert pii_row[12] == 0.78

    perf_call = fake.executemany_calls[2]
    assert perf_call[1][0][0] == "IBM-42"
    path.unlink()


def test_ibm_hr_seed_skips_when_not_staged(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "IBM_HR_CSV", tmp_path / "missing.csv")
    fake = FakePgClient()
    monkeypatch.setattr(m, "pg_client", fake)
    asyncio.run(m.seed_ibm_hr_dataset(FakePQC()))
    assert fake.executemany_calls == []     # no crash, no-op when file absent


UCI_HEADER = [
    "number", "incident_state", "opened_at", "priority", "category", "assignment_group",
]


def _write_uci_csv(rows):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=UCI_HEADER)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    f.close()
    return Path(f.name)


def test_uci_incident_seed_maps_fields(monkeypatch):
    rows = [
        {"number": "INC1", "incident_state": "New", "opened_at": "1/3/2016 10:00",
         "priority": "1 - Critical", "category": "Category 5", "assignment_group": "Group 7"},
        {"number": "INC1", "incident_state": "Closed", "opened_at": "2/3/2016 10:00",
         "priority": "1 - Critical", "category": "Category 5", "assignment_group": "Group 7"},
        {"number": "INC2", "incident_state": "Active", "opened_at": "3/3/2016 11:30",
         "priority": "3 - Moderate", "category": "Category 9", "assignment_group": "Group 2"},
    ]
    path = _write_uci_csv(rows)
    monkeypatch.setattr(m, "UCI_INCIDENT_CSV", path)
    fake = FakePgClient()
    monkeypatch.setattr(m, "pg_client", fake)
    import random
    random.seed(0)

    asyncio.run(m.seed_uci_incident_tickets(limit=10))

    query, inserted = fake.executemany_calls[0]
    assert "hrsd_tickets" in query
    ids = {r[0] for r in inserted}
    assert ids == {"UCI-INC1", "UCI-INC2"}   # deduped by incident number
    for r in inserted:
        assert r[2] in ("NEW", "IN_TRIAGE", "IN_RESOLUTION", "CLOSED")   # valid TicketStatus value
        assert r[4] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")             # valid TicketPriority value
        meta = json.loads(r[7])
        assert meta["source"] == "uci_incident_log"
    path.unlink()


def test_uci_incident_seed_skips_when_not_staged(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "UCI_INCIDENT_CSV", tmp_path / "missing.csv")
    fake = FakePgClient()
    monkeypatch.setattr(m, "pg_client", fake)
    asyncio.run(m.seed_uci_incident_tickets())
    assert fake.executemany_calls == []


if __name__ == "__main__":
    import sys as _sys
    import pytest
    _sys.exit(pytest.main([__file__, "-q"]))
