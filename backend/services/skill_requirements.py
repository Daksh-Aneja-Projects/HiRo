"""What each department needs its people to be able to do.

Shared by the planning service, which measures coverage against this, and
scripts/seed_skills.py, which builds the skill profiles. Keeping one list means
a department cannot be short of a skill that nobody was ever given.
"""
from typing import Dict, List

REQUIRED_SKILLS: Dict[str, List[str]] = {
    "Engineering": ["Software Design", "Testing and QA", "Code Review", "System Architecture",
                    "Cloud Infrastructure", "Incident Response", "Security Practices", "Mentoring"],
    "Research & Development": ["Experimental Design", "Statistics", "Technical Writing",
                               "Data Analysis", "Prototyping", "Literature Review", "Grant Writing"],
    "Sales": ["Prospecting", "Negotiation", "CRM Discipline", "Forecasting",
              "Territory Planning", "Contract Structuring", "Account Strategy"],
    "Marketing": ["Positioning", "Content Strategy", "Campaign Analytics", "Brand Management",
                  "Market Research", "Partner Marketing"],
    "Finance": ["Financial Modelling", "Budgeting", "Audit Readiness", "Reporting Standards",
                "Treasury Management", "Cost Control", "Board Reporting"],
    "Legal": ["Contract Drafting", "Regulatory Analysis", "Risk Assessment", "Litigation Management",
              "Data Protection Law", "Employment Law"],
    "Operations": ["Process Design", "Vendor Management", "Capacity Planning",
                   "Quality Assurance", "Continuous Improvement", "Logistics"],
    "Human Resources": ["Employee Relations", "Policy Analysis", "Compensation Design",
                        "Talent Acquisition", "Workforce Planning", "Employment Law",
                        "Coaching", "Organisational Design"],
    "IT": ["Network Administration", "Endpoint Management", "Identity and Access",
           "Security Monitoring", "Service Desk Operations", "Disaster Recovery"],
    "Support": ["Customer Communication", "Troubleshooting", "Escalation Handling",
                "Knowledge Base Authoring", "Service Level Management"],
    "HRIT": ["HRIS Administration", "Systems Integration", "Data Governance",
             "Reporting and Analytics", "Change Management", "Vendor Management"],
    "Executive": ["Strategic Planning", "Capital Allocation", "Stakeholder Management",
                  "Organisational Design", "Public Communication"],
}
