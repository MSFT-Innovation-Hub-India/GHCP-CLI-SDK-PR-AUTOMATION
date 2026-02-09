"""
Change Management MCP Server
============================
Provides approval matrix evaluation for fleet compliance PRs.
Implements CM-7 Change Management Approval Matrix policy.

Now uses the Model Context Protocol (MCP) via FastMCP + SSE transport.

MCP Tools:
    evaluate_approval  - Evaluate required approvals for a change
    assess_risk        - Calculate change risk score

Run:
    python server.py                          # default port 4101
    MCP_PORT=4101 python server.py            # explicit port
"""

import logging
import json
import structlog
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional

from mcp.server.fastmcp import FastMCP

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)
log = structlog.get_logger()

# Create the MCP server
import os as _os
_port = int(_os.getenv("MCP_PORT", "4101"))
mcp = FastMCP("Change Management MCP Server", host="0.0.0.0", port=_port)

# =============================================================================
# ENUMS
# =============================================================================

class ChangeType(str, Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    SECURITY_PATCH = "security_patch"
    OBSERVABILITY = "observability"
    INFRASTRUCTURE = "infrastructure"
    COMPLIANCE = "compliance"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# =============================================================================
# APPROVAL MATRIX CONFIGURATION (CM-7 Policy Implementation)
# =============================================================================

# High-impact services requiring SRE approval
HIGH_IMPACT_SERVICES = {
    "payments", "billing", "auth", "identity", "gateway", "core", "banking"
}

# Sensitive file patterns requiring Security approval
SECURITY_SENSITIVE_PATTERNS = [
    "auth", "secret", "keyvault", "credential", "token", "key",
    "password", "cert", "ssl", "tls", "encrypt", "decrypt",
    "oauth", "saml", "jwt", "identity", "permission", "rbac"
]

# Infrastructure patterns requiring SRE approval
INFRA_PATTERNS = [
    "docker", "kubernetes", "k8s", "helm", "terraform", "pulumi",
    "deploy", "pipeline", "ci", "cd", ".github/workflows", "infra"
]

# Database patterns requiring DBA review
DATABASE_PATTERNS = [
    "migration", "schema", "alembic", "sql", "database", "db", "model"
]

# =============================================================================
# BUSINESS LOGIC
# =============================================================================

def _is_high_impact_service(service: str) -> bool:
    """Check if service is classified as high-impact (CM-7.2)."""
    s_lower = service.lower()
    return any(hi in s_lower for hi in HIGH_IMPACT_SERVICES)

def _touches_sensitive_files(paths: List[str]) -> bool:
    """Check if any paths touch security-sensitive files (CM-7.3)."""
    paths_lower = [p.lower() for p in paths]
    return any(
        any(pattern in path for pattern in SECURITY_SENSITIVE_PATTERNS)
        for path in paths_lower
    )

def _touches_infrastructure(paths: List[str]) -> bool:
    """Check if any paths touch infrastructure files (CM-7.4)."""
    paths_lower = [p.lower() for p in paths]
    return any(
        any(pattern in path for pattern in INFRA_PATTERNS)
        for path in paths_lower
    )

def _touches_database(paths: List[str]) -> bool:
    """Check if any paths touch database/migration files (CM-7.5)."""
    paths_lower = [p.lower() for p in paths]
    return any(
        any(pattern in path for pattern in DATABASE_PATTERNS)
        for path in paths_lower
    )

def _calculate_risk_level(
    high_impact: bool,
    sensitive_files: bool,
    infra_touched: bool,
    db_touched: bool,
) -> RiskLevel:
    """Calculate risk level based on change characteristics."""
    score = sum([
        high_impact * 3,
        sensitive_files * 3,
        infra_touched * 2,
        db_touched * 2,
    ])
    if score >= 6:
        return RiskLevel.CRITICAL
    elif score >= 4:
        return RiskLevel.HIGH
    elif score >= 2:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW

def _get_sla_hours(risk_level: RiskLevel) -> int:
    """Get SLA for review based on risk level."""
    sla_map = {
        RiskLevel.LOW: 48,
        RiskLevel.MEDIUM: 24,
        RiskLevel.HIGH: 8,
        RiskLevel.CRITICAL: 4,
    }
    return sla_map[risk_level]

# =============================================================================
# MCP TOOLS
# =============================================================================

@mcp.tool()
def evaluate_approval(
    service: str,
    touched_paths: list[str] | None = None,
    change_type: str = "compliance",
    description: str = "",
) -> str:
    """
    Evaluate required approvals for a change based on CM-7 policy.

    Rules:
    - High-impact services (payments/auth/billing) -> SRE-Prod required
    - Security-sensitive file patterns -> Security team required
    - Infrastructure changes -> SRE-Prod required
    - Database/migration changes -> DBA review required
    - Observability-only changes -> ServiceOwner sufficient

    Args:
        service: Service name (e.g. contoso-payments-api)
        touched_paths: List of file paths modified
        change_type: Type of change (feature, bugfix, security_patch, observability, infrastructure, compliance)
        description: Change description
    """
    if touched_paths is None:
        touched_paths = []

    log.info("evaluating_approval", service=service, paths_count=len(touched_paths))

    high_impact = _is_high_impact_service(service)
    sensitive_files = _touches_sensitive_files(touched_paths)
    infra_touched = _touches_infrastructure(touched_paths)
    db_touched = _touches_database(touched_paths)

    required_approvals: List[str] = []
    policies_referenced: List[str] = ["CM-7"]
    rationale_parts: List[str] = []

    if high_impact:
        required_approvals.append("SRE-Prod")
        rationale_parts.append("High-impact service requires SRE oversight")
        policies_referenced.append("CM-7.2")

    if sensitive_files:
        if "Security" not in required_approvals:
            required_approvals.append("Security")
        rationale_parts.append("Security-sensitive files require Security team review")
        policies_referenced.append("CM-7.3")

    if infra_touched:
        if "SRE-Prod" not in required_approvals:
            required_approvals.append("SRE-Prod")
        rationale_parts.append("Infrastructure changes require SRE review")
        policies_referenced.append("CM-7.4")

    if db_touched:
        required_approvals.append("DBA")
        rationale_parts.append("Database/schema changes require DBA review")
        policies_referenced.append("CM-7.5")

    if not required_approvals:
        required_approvals.append("ServiceOwner")
        rationale_parts.append("Standard change with no elevated risk factors")

    risk_level = _calculate_risk_level(high_impact, sensitive_files, infra_touched, db_touched)
    auto_merge_allowed = risk_level == RiskLevel.LOW and not high_impact

    response = {
        "required_approvals": required_approvals,
        "rationale": "; ".join(rationale_parts),
        "risk_level": risk_level.value,
        "auto_merge_allowed": auto_merge_allowed,
        "sla_hours": _get_sla_hours(risk_level),
        "policies_referenced": list(set(policies_referenced)),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    log.info(
        "approval_evaluated",
        service=service,
        approvals=required_approvals,
        risk_level=risk_level.value,
    )

    return json.dumps(response, indent=2)


@mcp.tool()
def assess_risk(
    service: str,
    touched_paths: list[str] | None = None,
    lines_added: int = 0,
    lines_removed: int = 0,
    has_tests: bool = True,
    dependencies_changed: bool = False,
) -> str:
    """
    Calculate detailed risk score for a proposed change.
    Used to prioritize review queue and set SLAs.

    Args:
        service: Service name
        touched_paths: List of modified file paths
        lines_added: Number of lines added
        lines_removed: Number of lines removed
        has_tests: Whether tests are included
        dependencies_changed: Whether dependencies were modified
    """
    if touched_paths is None:
        touched_paths = []

    log.info("assessing_risk", service=service)

    risk_factors: List[str] = []
    mitigations: List[str] = []
    score = 0

    if _is_high_impact_service(service):
        score += 25
        risk_factors.append("High-impact service")
        mitigations.append("Require canary deployment")

    if _touches_sensitive_files(touched_paths):
        score += 25
        risk_factors.append("Security-sensitive files modified")
        mitigations.append("Security team review required")

    total_lines = lines_added + lines_removed
    if total_lines > 500:
        score += 20
        risk_factors.append(f"Large change ({total_lines} lines)")
        mitigations.append("Consider splitting into smaller PRs")
    elif total_lines > 200:
        score += 10
        risk_factors.append(f"Medium change ({total_lines} lines)")

    if not has_tests:
        score += 15
        risk_factors.append("No tests included")
        mitigations.append("Add unit tests before merge")

    if dependencies_changed:
        score += 10
        risk_factors.append("Dependencies modified")
        mitigations.append("Run security scan on new dependencies")

    if _touches_infrastructure(touched_paths):
        score += 15
        risk_factors.append("Infrastructure changes")
        mitigations.append("Validate in staging environment first")

    if score >= 70:
        risk_level = RiskLevel.CRITICAL
    elif score >= 50:
        risk_level = RiskLevel.HIGH
    elif score >= 25:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.LOW

    response = {
        "risk_score": min(score, 100),
        "risk_level": risk_level.value,
        "risk_factors": risk_factors if risk_factors else ["No significant risk factors identified"],
        "mitigations_recommended": mitigations if mitigations else ["Standard review process sufficient"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return json.dumps(response, indent=2)


# =============================================================================
# MCP RESOURCES  (lightweight read-only info exposed via MCP)
# =============================================================================

@mcp.resource("health://status")
def healthz() -> str:
    """Health check - process is alive."""
    return json.dumps({
        "status": "ok",
        "service": "change-mgmt-mcp",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@mcp.resource("health://ready")
def readyz() -> str:
    """Readiness check - service ready to accept requests."""
    return json.dumps({
        "status": "ready",
        "service": "change-mgmt-mcp",
        "version": "1.0.0",
        "checks": {
            "approval_matrix": "loaded",
            "policy_config": "valid",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    print(f"Change Management MCP server starting on port {_port} (SSE transport)")
    mcp.run(transport="sse")
