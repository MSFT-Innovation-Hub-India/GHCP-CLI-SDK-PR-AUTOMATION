"""
Change Management MCP Server
============================
Provides approval matrix evaluation for fleet compliance PRs.
Implements CM-7 Change Management Approval Matrix policy.

Endpoints:
    POST /approval - Evaluate required approvals for a change
    POST /risk-assessment - Calculate change risk score
    GET /healthz - Health check
    GET /readyz - Readiness check
"""

import logging
import structlog
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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

app = FastAPI(
    title="Change Management MCP Server",
    description="Evaluates approval requirements based on CM-7 policy matrix",
    version="1.0.0",
)

# =============================================================================
# MODELS
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

class ApprovalReq(BaseModel):
    """Request to evaluate required approvals for a change."""
    service: str = Field(..., description="Service name (e.g., contoso-payments-api)")
    touched_paths: List[str] = Field(default_factory=list, description="List of file paths modified")
    change_type: Optional[ChangeType] = Field(default=ChangeType.COMPLIANCE, description="Type of change")
    description: Optional[str] = Field(default="", description="Change description")

class ApprovalResponse(BaseModel):
    """Response containing required approvals and rationale."""
    required_approvals: List[str]
    rationale: str
    risk_level: RiskLevel
    auto_merge_allowed: bool
    sla_hours: int
    policies_referenced: List[str]
    timestamp: str

class RiskAssessmentReq(BaseModel):
    """Request for risk assessment of a proposed change."""
    service: str
    touched_paths: List[str] = Field(default_factory=list)
    lines_added: int = Field(default=0, ge=0)
    lines_removed: int = Field(default=0, ge=0)
    has_tests: bool = Field(default=True)
    dependencies_changed: bool = Field(default=False)

class RiskAssessmentResponse(BaseModel):
    """Risk assessment result."""
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    risk_factors: List[str]
    mitigations_recommended: List[str]
    timestamp: str

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
    db_touched: bool
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
# ENDPOINTS
# =============================================================================

@app.post("/approval", response_model=ApprovalResponse)
def evaluate_approval(req: ApprovalReq) -> ApprovalResponse:
    """
    Evaluate required approvals for a change based on CM-7 policy.
    
    Rules:
    - High-impact services (payments/auth/billing) → SRE-Prod required
    - Security-sensitive file patterns → Security team required
    - Infrastructure changes → SRE-Prod required
    - Database/migration changes → DBA review required
    - Observability-only changes → ServiceOwner sufficient
    """
    log.info("evaluating_approval", service=req.service, paths_count=len(req.touched_paths))
    
    high_impact = _is_high_impact_service(req.service)
    sensitive_files = _touches_sensitive_files(req.touched_paths)
    infra_touched = _touches_infrastructure(req.touched_paths)
    db_touched = _touches_database(req.touched_paths)
    
    required_approvals: List[str] = []
    policies_referenced: List[str] = ["CM-7"]
    rationale_parts: List[str] = []
    
    # Evaluate each dimension
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
    
    # Default: ServiceOwner if no elevated approvals needed
    if not required_approvals:
        required_approvals.append("ServiceOwner")
        rationale_parts.append("Standard change with no elevated risk factors")
    
    risk_level = _calculate_risk_level(high_impact, sensitive_files, infra_touched, db_touched)
    
    # Automation policy: agents may open PRs but NOT auto-merge to production
    auto_merge_allowed = risk_level == RiskLevel.LOW and not high_impact
    
    response = ApprovalResponse(
        required_approvals=required_approvals,
        rationale="; ".join(rationale_parts),
        risk_level=risk_level,
        auto_merge_allowed=auto_merge_allowed,
        sla_hours=_get_sla_hours(risk_level),
        policies_referenced=list(set(policies_referenced)),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    
    log.info(
        "approval_evaluated",
        service=req.service,
        approvals=required_approvals,
        risk_level=risk_level.value,
    )
    
    return response


@app.post("/risk-assessment", response_model=RiskAssessmentResponse)
def assess_risk(req: RiskAssessmentReq) -> RiskAssessmentResponse:
    """
    Calculate detailed risk score for a proposed change.
    Used to prioritize review queue and set SLAs.
    """
    log.info("assessing_risk", service=req.service)
    
    risk_factors: List[str] = []
    mitigations: List[str] = []
    score = 0
    
    # Service criticality
    if _is_high_impact_service(req.service):
        score += 25
        risk_factors.append("High-impact service")
        mitigations.append("Require canary deployment")
    
    # Sensitive files
    if _touches_sensitive_files(req.touched_paths):
        score += 25
        risk_factors.append("Security-sensitive files modified")
        mitigations.append("Security team review required")
    
    # Change size
    total_lines = req.lines_added + req.lines_removed
    if total_lines > 500:
        score += 20
        risk_factors.append(f"Large change ({total_lines} lines)")
        mitigations.append("Consider splitting into smaller PRs")
    elif total_lines > 200:
        score += 10
        risk_factors.append(f"Medium change ({total_lines} lines)")
    
    # Test coverage
    if not req.has_tests:
        score += 15
        risk_factors.append("No tests included")
        mitigations.append("Add unit tests before merge")
    
    # Dependencies
    if req.dependencies_changed:
        score += 10
        risk_factors.append("Dependencies modified")
        mitigations.append("Run security scan on new dependencies")
    
    # Infrastructure
    if _touches_infrastructure(req.touched_paths):
        score += 15
        risk_factors.append("Infrastructure changes")
        mitigations.append("Validate in staging environment first")
    
    # Determine risk level
    if score >= 70:
        risk_level = RiskLevel.CRITICAL
    elif score >= 50:
        risk_level = RiskLevel.HIGH
    elif score >= 25:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.LOW
    
    return RiskAssessmentResponse(
        risk_score=min(score, 100),
        risk_level=risk_level,
        risk_factors=risk_factors if risk_factors else ["No significant risk factors identified"],
        mitigations_recommended=mitigations if mitigations else ["Standard review process sufficient"],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    """Health check endpoint - process is alive."""
    return {
        "status": "ok",
        "service": "change-mgmt-mcp",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/readyz")
def readyz() -> Dict[str, Any]:
    """Readiness check endpoint - service ready to accept requests."""
    return {
        "status": "ready",
        "service": "change-mgmt-mcp",
        "version": "1.0.0",
        "checks": {
            "approval_matrix": "loaded",
            "policy_config": "valid",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
