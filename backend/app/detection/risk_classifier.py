"""
Risk Classification Engine
Combines all six technique results into a final invoice classification and risk level.
This is the single authoritative policy component — avoid scattered hardcoded rules.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Technique names (canonical)
T_GST = "gst_validation"
T_DUP = "duplicate_detection"
T_ZSCORE = "zscore_analysis"
T_SUPPLIER = "supplier_behavior"
T_FREQ = "transaction_frequency"
T_IF = "isolation_forest"

# Statuses
STATUS_PASS = "Pass"
STATUS_FLAGGED = "Flagged"
STATUS_INSUFFICIENT = "Insufficient Data"
STATUS_ERROR = "Error"

# Severity weights: used to escalate risk level
SEVERITY_WEIGHTS = {
    "High": 3,
    "Medium": 2,
    "Low": 1,
    "None": 0,
}

# Per-technique contribution to risk escalation
# Maps (technique, severity) -> risk_points
TECHNIQUE_RISK_POLICY: Dict[str, Dict[str, int]] = {
    T_GST: {"High": 5, "Medium": 3, "Low": 1},
    T_DUP: {"High": 6, "Medium": 4, "Low": 2},
    T_ZSCORE: {"High": 4, "Medium": 2, "Low": 1},
    T_SUPPLIER: {"High": 4, "Medium": 2, "Low": 1},
    T_FREQ: {"High": 3, "Medium": 2, "Low": 1},
    T_IF: {"High": 3, "Medium": 2, "Low": 1},
}

# Thresholds
HIGH_RISK_THRESHOLD = 5
MEDIUM_RISK_THRESHOLD = 2
SUSPICIOUS_THRESHOLD = 2   # points >= this means Suspicious classification


def classify_invoice(
    findings: List[Dict[str, Any]]
) -> Tuple[str, str, str]:
    """
    Args:
        findings: list of dicts with keys: technique, status, severity

    Returns:
        (classification, risk_level, summary)
        classification: "Suspicious" | "Not Suspicious"
        risk_level: "High" | "Medium" | "Low"
        summary: human-readable explanation
    """
    risk_points = 0
    flagged_count = 0
    flagged_techniques = []
    high_severity_flags = []

    for f in findings:
        technique = f.get("technique", "unknown")
        status = f.get("status", STATUS_PASS)
        severity = f.get("severity", "None")

        if status == STATUS_FLAGGED:
            flagged_count += 1
            flagged_techniques.append(technique)
            points = TECHNIQUE_RISK_POLICY.get(technique, {}).get(severity, 0)
            risk_points += points
            if severity == "High":
                high_severity_flags.append(technique)

    # Determine classification
    classification = "Suspicious" if risk_points >= SUSPICIOUS_THRESHOLD else "Not Suspicious"

    # Determine risk level
    if risk_points >= HIGH_RISK_THRESHOLD or len(high_severity_flags) >= 1:
        risk_level = "High"
    elif risk_points >= MEDIUM_RISK_THRESHOLD:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    # Build summary
    if flagged_count == 0:
        summary = (
            "No significant issues were identified by the techniques that could be evaluated. "
            "This assessment is based on available data and does not rule out all forms of fraud."
        )
    else:
        names = ", ".join(
            t.replace("_", " ").title() for t in flagged_techniques
        )
        summary = (
            f"{flagged_count} of {len(findings)} technique(s) raised findings: {names}. "
            f"Risk score: {risk_points}. "
            "This assessment indicates areas requiring review, not confirmed fraud."
        )

    return classification, risk_level, summary
