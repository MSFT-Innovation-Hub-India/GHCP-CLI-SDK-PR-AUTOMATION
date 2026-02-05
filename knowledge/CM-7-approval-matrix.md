# CM-7 Change Management Approval Matrix

**Policy ID:** CM-7  
**Category:** Change Management  
**Status:** Active  
**Effective Date:** 2024-01-01  
**Last Review:** 2025-06-15  
**Owner:** Platform Engineering & SRE  

---

## 1. Purpose & Scope

### 1.1 Purpose
Define approval requirements for changes based on:
- Service criticality
- Change type and scope
- Risk assessment
- Compliance requirements

### 1.2 Scope
All changes to production and pre-production systems including:
- Application code changes
- Configuration changes
- Infrastructure changes
- Database schema changes
- Dependency updates

---

## 2. Service Classification

### 2.1 Tier Definitions

| Tier | Description | Examples | SLA |
|------|-------------|----------|-----|
| **Tier 1 (Critical)** | Revenue-impacting, customer-facing, auth/identity | Payments, Auth, Checkout, Gateway | 99.99% |
| **Tier 2 (High)** | Important internal services, data processing | Orders, Inventory, Analytics | 99.9% |
| **Tier 3 (Standard)** | Supporting services, tools | Notifications, Admin UI, Reporting | 99.5% |
| **Tier 4 (Low)** | Development tools, internal utilities | Dev environments, CI/CD helpers | 99% |

### 2.2 High-Impact Service Keywords
Services containing these keywords are automatically classified as high-impact:
- `payment`, `billing`, `checkout`, `transaction`
- `auth`, `identity`, `login`, `session`
- `gateway`, `api-gateway`, `edge`
- `core`, `platform`, `foundation`
- `customer`, `user`, `account`

---

## 3. Approval Matrix

### 3.1 Standard Changes

| Change Type | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|-------------|--------|--------|--------|--------|
| Bug fix (no data/API change) | SRE + ServiceOwner | ServiceOwner | ServiceOwner | Auto |
| Feature (backward compatible) | SRE + ServiceOwner | ServiceOwner | ServiceOwner | ServiceOwner |
| Feature (breaking change) | SRE + Security + PM | SRE + ServiceOwner | ServiceOwner | ServiceOwner |
| Observability only | ServiceOwner | ServiceOwner | Auto | Auto |
| Documentation only | Auto | Auto | Auto | Auto |

### 3.2 Security-Sensitive Changes

Changes touching these patterns require **Security team approval**:

| Pattern | Examples |
|---------|----------|
| Authentication/Authorization | `auth/`, `login/`, `session/`, `token/` |
| Secrets Management | `secret/`, `credential/`, `keyvault/`, `vault/` |
| Cryptography | `encrypt/`, `decrypt/`, `hash/`, `sign/` |
| Access Control | `permission/`, `rbac/`, `role/`, `policy/` |
| PII/Sensitive Data | `pii/`, `personal/`, `ssn/`, `payment/` |

### 3.3 Infrastructure Changes

| Change Type | Required Approvals |
|-------------|-------------------|
| Kubernetes manifests | SRE-Prod |
| Terraform/Pulumi | SRE-Prod + Security (if network/IAM) |
| CI/CD pipelines | SRE-Prod |
| Docker/container config | ServiceOwner |
| Network/firewall rules | SRE-Prod + Security |
| IAM/RBAC changes | Security + SRE-Prod |

### 3.4 Database Changes

| Change Type | Required Approvals |
|-------------|-------------------|
| Schema migration (additive) | DBA + ServiceOwner |
| Schema migration (destructive) | DBA + SRE-Prod + ServiceOwner |
| Index changes | DBA |
| Stored procedure changes | DBA + ServiceOwner |
| Data backfill/migration | DBA + SRE-Prod |

---

## 4. Decision Flowchart

```
START: PR submitted
│
├─► Is it documentation only?
│   └─► YES → Auto-approve (CI passes)
│
├─► Does it touch security-sensitive files?
│   └─► YES → Require: Security + [Standard rules]
│
├─► Does it touch infrastructure (k8s, terraform, CI)?
│   └─► YES → Require: SRE-Prod + [Standard rules]
│
├─► Does it touch database/migrations?
│   └─► YES → Require: DBA + [Standard rules]
│
├─► Is the service Tier 1 (Critical)?
│   └─► YES → Require: SRE-Prod + ServiceOwner
│
├─► Is it observability-only (logging, metrics, tracing)?
│   └─► YES → Require: ServiceOwner (Tier 1-2) or Auto (Tier 3-4)
│
└─► Standard change
    └─► Require: ServiceOwner
```

---

## 5. Automation Policy

### 5.1 What Agents CAN Do

| Action | Allowed |
|--------|---------|
| Clone repositories | ✅ |
| Create branches | ✅ |
| Run tests locally | ✅ |
| Run linters/scanners | ✅ |
| Apply code fixes | ✅ |
| Open Pull Requests | ✅ |
| Add labels to PRs | ✅ |
| Request reviews | ✅ |
| Run CI pipelines | ✅ |
| Comment on PRs | ✅ |

### 5.2 What Agents MUST NOT Do

| Action | Prohibited |
|--------|------------|
| Merge to main/production | ❌ |
| Direct push to protected branches | ❌ |
| Bypass required reviews | ❌ |
| Auto-approve security changes | ❌ |
| Modify approval requirements | ❌ |
| Access production secrets | ❌ |

### 5.3 Human-in-the-Loop Requirements
Every PR to production branches MUST have:
- At least 1 human review approval
- Human-triggered merge action
- Audit trail of approver identity

---

## 6. Implementation

### 6.1 Approval Matrix Evaluation (Python)

```python
from dataclasses import dataclass
from enum import Enum
from typing import List, Set

class ServiceTier(Enum):
    CRITICAL = 1
    HIGH = 2
    STANDARD = 3
    LOW = 4

@dataclass
class ApprovalResult:
    required_approvals: List[str]
    rationale: str
    risk_level: str
    sla_hours: int
    auto_merge_allowed: bool

# High-impact service keywords
HIGH_IMPACT_KEYWORDS = {
    "payment", "billing", "checkout", "transaction",
    "auth", "identity", "login", "session",
    "gateway", "core", "platform",
}

# Security-sensitive path patterns
SECURITY_PATTERNS = [
    "auth", "secret", "credential", "keyvault",
    "token", "password", "encrypt", "sign",
    "permission", "rbac", "role", "policy",
]

# Infrastructure patterns
INFRA_PATTERNS = [
    "docker", "kubernetes", "k8s", "helm",
    "terraform", "pulumi", ".github/workflows",
    "deploy", "infra", "pipeline",
]

# Database patterns
DB_PATTERNS = [
    "migration", "schema", "alembic", "sql",
    "database", "model",
]

def evaluate_approvals(
    service: str,
    touched_paths: List[str],
    change_type: str = "standard",
) -> ApprovalResult:
    """Evaluate required approvals per CM-7 policy."""
    
    required: Set[str] = set()
    rationale_parts: List[str] = []
    
    # Determine service tier
    service_lower = service.lower()
    is_high_impact = any(kw in service_lower for kw in HIGH_IMPACT_KEYWORDS)
    
    # Normalize paths
    paths_lower = [p.lower() for p in touched_paths]
    
    # Check security-sensitive
    if any(any(pat in p for pat in SECURITY_PATTERNS) for p in paths_lower):
        required.add("Security")
        rationale_parts.append("Security-sensitive files modified")
    
    # Check infrastructure
    if any(any(pat in p for pat in INFRA_PATTERNS) for p in paths_lower):
        required.add("SRE-Prod")
        rationale_parts.append("Infrastructure changes require SRE review")
    
    # Check database
    if any(any(pat in p for pat in DB_PATTERNS) for p in paths_lower):
        required.add("DBA")
        rationale_parts.append("Database changes require DBA review")
    
    # Check high-impact service
    if is_high_impact:
        required.add("SRE-Prod")
        rationale_parts.append("High-impact service requires SRE oversight")
    
    # Default to ServiceOwner if no elevated requirements
    if not required:
        required.add("ServiceOwner")
        rationale_parts.append("Standard change")
    
    # Calculate risk level and SLA
    risk_level = "high" if len(required) > 1 else "medium" if required != {"ServiceOwner"} else "low"
    sla_map = {"high": 4, "medium": 24, "low": 48}
    
    return ApprovalResult(
        required_approvals=sorted(required),
        rationale="; ".join(rationale_parts),
        risk_level=risk_level,
        sla_hours=sla_map[risk_level],
        auto_merge_allowed=risk_level == "low" and not is_high_impact,
    )
```

### 6.2 GitHub PR Labels

Map approvals to PR labels for visibility:

| Required Approval | PR Label |
|------------------|----------|
| SRE-Prod | `needs-sre-approval` |
| Security | `needs-security-approval` |
| DBA | `needs-dba-approval` |
| ServiceOwner | `ready-for-review` |

---

## 7. Emergency Changes

### 7.1 Emergency Process
For production incidents requiring immediate fix:

1. **Declare Emergency** - Page on-call SRE
2. **Expedited Review** - Single SRE approval (verbal OK, documented after)
3. **Deploy Fix** - With monitoring
4. **Post-Incident** - Full review within 24 hours, formal approval retroactively

### 7.2 Emergency Change Criteria
- Active production incident (P1/P2)
- Customer-impacting issue
- Security breach response
- Compliance deadline

---

## 8. Audit & Compliance

### 8.1 Audit Trail Requirements
All changes MUST have:
- PR with full history
- Approver identity (GitHub user)
- Approval timestamp
- CI/CD run logs
- Deployment record

### 8.2 Compliance Mappings

| Framework | CM-7 Coverage |
|-----------|---------------|
| SOC2 CC8.1 | Change management controls |
| ISO27001 A.12.1.2 | Change management |
| PCI-DSS 6.4 | Change control procedures |

---

## 9. References

- [REL-1.0 PR Gates & Quality Bar](./REL-1.0-pr-gates.md)
- [SEC-2.4 Dependency Vulnerability Response](./SEC-2.4-dependency-vulnerability-response.md)
- [GitHub Protected Branches Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches)
