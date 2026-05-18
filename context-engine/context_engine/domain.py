"""Business domain inference from table names and column semantics."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# Domain keyword mappings: domain_name → list of regex patterns
_DOMAIN_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("HR/Human Resources", [
        r"employee", r"emp_", r"hr_", r"attrition", r"performance",
        r"hire", r"termination", r"payroll", r"benefit", r"leave",
        r"recruitment", r"onboarding", r"talent", r"compensation",
        r"gender", r"marital", r"ethnicity", r"department", r"dept_",
        r"monthly_salary", r"annual_salary", r"base_salary", r"bonus",
    ]),
    ("Sales/Business", [
        r"sale", r"order", r"revenue", r"customer", r"cust_", r"client",
        r"product", r"item", r"sku", r"invoice", r"payment", r"purchase",
        r"pricing", r"discount", r"commission", r"quote", r"lead",
        r"opportunity", r"deal", r"pipeline", r"conversion",
    ]),
    ("Finance", [
        r"finance", r"budget", r"expense", r"cost", r"gl_", r"ledger",
        r"account", r"asset", r"liability", r"equity", r"tax",
        r"depreciation", r"amortization", r"cashflow", r"balance_sheet",
    ]),
    ("Project Management", [
        r"project", r"task", r"sprint", r"epic", r"story", r"milestone",
        r"issue", r"ticket", r"scrum", r"kanban", r"deliverable",
        r"timeline", r"gantt", r"resource_allocat",
    ]),
    ("Marketing", [
        r"campaign", r"channel", r"impression", r"click", r"conversion",
        r"attribution", r"segment", r"audience", r"engagement",
        r"roi", r"cpa", r"cpc", r"cpm", r"funnel",
    ]),
    ("Supply Chain", [
        r"inventory", r"warehouse", r"shipment", r"supplier", r"vendor",
        r"procurement", r"logistics", r"stock", r"reorder", r"lead_time",
    ]),
    ("Analytics/Telemetry", [
        r"event", r"metric", r"log", r"session", r"page_view",
        r"user_behavior", r"clickstream", r"funnel_step", r"a_b_test",
    ]),
    ("Education", [
        r"student", r"course", r"enrollment", r"grade", r"exam",
        r"subject", r"semester", r"faculty", r"classroom", r"curriculum",
    ]),
    ("Healthcare", [
        r"patient", r"diagnosis", r"treatment", r"prescription",
        r"visit", r"admission", r"clinical", r"lab_result", r"procedure",
    ]),
]


def infer_domain(
    table_names: List[str],
    column_names: Optional[List[str]] = None,
) -> Tuple[str, List[str]]:
    """Infer the business domain from table and column names.

    Returns (domain_name, list_of_matched_keywords).
    """
    all_names = list(table_names)
    if column_names:
        all_names.extend(column_names)

    scores: Dict[str, int] = {}
    matched: Dict[str, List[str]] = {}

    for domain, patterns in _DOMAIN_KEYWORDS:
        for pat in patterns:
            for name in all_names:
                import re
                if re.search(pat, name, re.IGNORECASE):
                    scores[domain] = scores.get(domain, 0) + 1
                    matched.setdefault(domain, []).append(pat)

    if not scores:
        return ("General Business", [])

    best_domain = max(scores, key=scores.get)
    return (best_domain, list(set(matched.get(best_domain, []))))


def generate_domain_summary(domain: str, table_names: List[str], key_features: List[str]) -> str:
    """Generate a one-line domain summary."""
    table_str = " and ".join(f"`{t}`" for t in table_names[:3])
    if len(table_names) > 3:
        table_str += f" and {len(table_names) - 3} more"

    feature_str = ""
    if key_features:
        feature_str = f" with {', '.join(key_features[:3])}"

    return f"This datasource contains {domain.lower()} data{feature_str}."
