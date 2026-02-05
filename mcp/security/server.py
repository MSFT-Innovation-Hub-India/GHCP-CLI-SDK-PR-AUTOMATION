"""
Security Scan MCP Server
========================
Provides dependency vulnerability scanning for fleet compliance.
Implements SEC-2.4 Dependency Vulnerability Response policy.

Endpoints:
    POST /scan - Scan dependencies for known vulnerabilities
    POST /scan-detailed - Detailed vulnerability analysis
    GET /vulnerability/{cve_id} - Get details for specific CVE
    GET /healthz - Health check
    GET /readyz - Readiness check
"""

import logging
import re
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
    title="Security Scan MCP Server",
    description="Scans dependencies for vulnerabilities per SEC-2.4 policy",
    version="1.0.0",
)

# =============================================================================
# MODELS
# =============================================================================

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class VulnerabilityFinding(BaseModel):
    """A single vulnerability finding."""
    name: str = Field(..., description="Package name")
    version: str = Field(..., description="Affected version")
    severity: Severity
    cve: str = Field(..., description="CVE identifier")
    cwe: Optional[str] = Field(None, description="CWE identifier")
    fixed_version: str = Field(..., description="First fixed version")
    title: str = Field(..., description="Vulnerability title")
    description: str = Field(..., description="Detailed description")
    cvss_score: float = Field(..., ge=0.0, le=10.0)
    attack_vector: str
    references: List[str] = Field(default_factory=list)
    published_date: str
    remediation_sla_hours: int

class ScanRequest(BaseModel):
    """Request to scan dependencies."""
    requirements: str = Field(default="", description="Contents of requirements.txt")
    lockfile: Optional[str] = Field(default=None, description="Contents of lockfile")

class ScanResponse(BaseModel):
    """Response from dependency scan."""
    findings: List[VulnerabilityFinding]
    summary: Dict[str, int]
    policy_compliant: bool
    policies_referenced: List[str]
    recommendations: List[str]
    timestamp: str

class DetailedScanRequest(BaseModel):
    """Request for detailed vulnerability analysis."""
    requirements: str = Field(default="", description="Contents of requirements.txt")
    include_transitive: bool = Field(default=True, description="Include transitive dependencies")
    severity_threshold: Severity = Field(default=Severity.LOW, description="Minimum severity to report")

class CVEDetail(BaseModel):
    """Full CVE details."""
    cve: str
    cwe: Optional[str]
    title: str
    description: str
    severity: Severity
    cvss_score: float
    attack_vector: str
    affected_packages: List[Dict[str, str]]
    references: List[str]
    published_date: str
    last_modified: str

# =============================================================================
# VULNERABILITY DATABASE (Simulated)
# Real implementation would query NVD, OSV, Snyk, etc.
# =============================================================================

VULNERABILITY_DB: Dict[str, List[Dict[str, Any]]] = {
    "requests": [
        {
            "version_range": "<2.25.0",
            "cve": "CVE-2023-32681",
            "cwe": "CWE-200",
            "severity": Severity.MEDIUM,
            "fixed_version": "2.31.0",
            "cvss_score": 6.1,
            "title": "Unintended leak of Proxy-Authorization header",
            "description": "Requests library leaks Proxy-Authorization header to destination servers when following cross-origin redirects.",
            "attack_vector": "NETWORK",
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2023-32681",
                "https://github.com/psf/requests/security/advisories/GHSA-j8r2-6x86-q33q"
            ],
            "published_date": "2023-05-26",
        },
        {
            "version_range": "<2.20.0",
            "cve": "CVE-2018-18074",
            "cwe": "CWE-522",
            "severity": Severity.HIGH,
            "fixed_version": "2.20.0",
            "cvss_score": 7.5,
            "title": "Session fixation vulnerability",
            "description": "The Requests package through 2.19.1 sends an HTTP Authorization header to an http URI upon receiving a same-hostname https-to-http redirect.",
            "attack_vector": "NETWORK",
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2018-18074"
            ],
            "published_date": "2018-10-09",
        },
    ],
    "pyyaml": [
        {
            "version_range": "<6.0",
            "cve": "CVE-2020-14343",
            "cwe": "CWE-20",
            "severity": Severity.CRITICAL,
            "fixed_version": "6.0.1",
            "cvss_score": 9.8,
            "title": "Arbitrary code execution via untrusted YAML",
            "description": "A vulnerability in PyYAML allows arbitrary code execution when loading untrusted YAML data using yaml.load() without specifying Loader=SafeLoader.",
            "attack_vector": "NETWORK",
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2020-14343",
                "https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation"
            ],
            "published_date": "2020-07-21",
        },
        {
            "version_range": "<5.4",
            "cve": "CVE-2020-1747",
            "cwe": "CWE-20",
            "severity": Severity.CRITICAL,
            "fixed_version": "5.4",
            "cvss_score": 9.8,
            "title": "Arbitrary code execution in FullLoader",
            "description": "PyYAML FullLoader class does not properly handle untrusted data, leading to arbitrary code execution.",
            "attack_vector": "NETWORK",
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2020-1747"
            ],
            "published_date": "2020-03-24",
        },
    ],
    "urllib3": [
        {
            "version_range": "<1.26.5",
            "cve": "CVE-2021-33503",
            "cwe": "CWE-400",
            "severity": Severity.HIGH,
            "fixed_version": "1.26.5",
            "cvss_score": 7.5,
            "title": "ReDoS via malicious URL",
            "description": "An issue was discovered in urllib3 where a malicious URL can cause a denial of service (ReDoS).",
            "attack_vector": "NETWORK",
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-33503"
            ],
            "published_date": "2021-06-29",
        },
    ],
    "cryptography": [
        {
            "version_range": "<41.0.0",
            "cve": "CVE-2023-38325",
            "cwe": "CWE-295",
            "severity": Severity.HIGH,
            "fixed_version": "41.0.2",
            "cvss_score": 7.5,
            "title": "NULL dereference in certificate parsing",
            "description": "The cryptography package before 41.0.2 has a potential denial of service vulnerability when parsing malicious X.509 certificates.",
            "attack_vector": "NETWORK",
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2023-38325"
            ],
            "published_date": "2023-07-14",
        },
    ],
    "pillow": [
        {
            "version_range": "<9.3.0",
            "cve": "CVE-2022-45198",
            "cwe": "CWE-787",
            "severity": Severity.HIGH,
            "fixed_version": "9.3.0",
            "cvss_score": 7.5,
            "title": "Heap buffer overflow in PhotoCD",
            "description": "Pillow before 9.3.0 is vulnerable to heap buffer overflow via crafted PhotoCD files.",
            "attack_vector": "LOCAL",
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2022-45198"
            ],
            "published_date": "2022-11-14",
        },
    ],
    "django": [
        {
            "version_range": "<4.2.4",
            "cve": "CVE-2023-41164",
            "cwe": "CWE-400",
            "severity": Severity.MEDIUM,
            "fixed_version": "4.2.4",
            "cvss_score": 5.3,
            "title": "Potential denial of service in django.utils.encoding.uri_to_iri",
            "description": "Django before 4.2.4 allows a potential denial of service via a very long URI passed to uri_to_iri().",
            "attack_vector": "NETWORK",
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2023-41164"
            ],
            "published_date": "2023-09-04",
        },
    ],
    "flask": [
        {
            "version_range": "<2.3.2",
            "cve": "CVE-2023-30861",
            "cwe": "CWE-539",
            "severity": Severity.HIGH,
            "fixed_version": "2.3.2",
            "cvss_score": 7.5,
            "title": "Cookie security bypass",
            "description": "Flask is vulnerable to possible disclosure of permanent session cookie if running without a SECRET_KEY in debug mode.",
            "attack_vector": "NETWORK",
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2023-30861"
            ],
            "published_date": "2023-05-02",
        },
    ],
    "jinja2": [
        {
            "version_range": "<3.1.2",
            "cve": "CVE-2024-22195",
            "cwe": "CWE-79",
            "severity": Severity.MEDIUM,
            "fixed_version": "3.1.3",
            "cvss_score": 6.1,
            "title": "XSS via xmlattr filter",
            "description": "Jinja2 before 3.1.3 is vulnerable to XSS when xmlattr filter is used with user-controlled keys.",
            "attack_vector": "NETWORK",
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2024-22195"
            ],
            "published_date": "2024-01-11",
        },
    ],
}

# SLA hours based on severity (SEC-2.4 policy)
SEVERITY_SLA = {
    Severity.CRITICAL: 24,
    Severity.HIGH: 72,
    Severity.MEDIUM: 168,  # 1 week
    Severity.LOW: 720,     # 30 days
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_requirements(requirements_text: str) -> Dict[str, str]:
    """Parse requirements.txt into dict of {package: version}."""
    deps: Dict[str, str] = {}
    for line in requirements_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Match patterns: package==version, package>=version, package
        match = re.match(r'^([a-zA-Z0-9_-]+)([<>=!]+)?(.+)?$', line)
        if match:
            pkg = match.group(1).lower().replace("-", "_")
            version = match.group(3) or "unknown"
            deps[pkg] = version.strip()
    return deps

def _version_match(installed: str, vuln_range: str) -> bool:
    """
    Check if installed version matches vulnerability range.
    Simplified version comparison for demo; real impl would use packaging.version
    """
    if installed == "unknown":
        return True  # Assume vulnerable if version unknown
    
    # Parse version range like "<2.25.0"
    match = re.match(r'^([<>=!]+)([0-9.]+)$', vuln_range)
    if not match:
        return False
    
    operator, threshold = match.groups()
    
    try:
        # Simple numeric comparison (real impl uses packaging.version)
        installed_parts = [int(x) for x in installed.split(".")]
        threshold_parts = [int(x) for x in threshold.split(".")]
        
        # Pad to same length
        max_len = max(len(installed_parts), len(threshold_parts))
        installed_parts.extend([0] * (max_len - len(installed_parts)))
        threshold_parts.extend([0] * (max_len - len(threshold_parts)))
        
        if operator == "<":
            return installed_parts < threshold_parts
        elif operator == "<=":
            return installed_parts <= threshold_parts
        elif operator == ">":
            return installed_parts > threshold_parts
        elif operator == ">=":
            return installed_parts >= threshold_parts
        elif operator == "==":
            return installed_parts == threshold_parts
    except ValueError:
        pass
    
    return False

def _check_package(pkg: str, version: str) -> List[VulnerabilityFinding]:
    """Check a single package for vulnerabilities."""
    findings: List[VulnerabilityFinding] = []
    
    pkg_normalized = pkg.lower().replace("-", "_")
    vulns = VULNERABILITY_DB.get(pkg_normalized, [])
    
    for vuln in vulns:
        if _version_match(version, vuln["version_range"]):
            findings.append(VulnerabilityFinding(
                name=pkg,
                version=version,
                severity=vuln["severity"],
                cve=vuln["cve"],
                cwe=vuln.get("cwe"),
                fixed_version=vuln["fixed_version"],
                title=vuln["title"],
                description=vuln["description"],
                cvss_score=vuln["cvss_score"],
                attack_vector=vuln["attack_vector"],
                references=vuln.get("references", []),
                published_date=vuln["published_date"],
                remediation_sla_hours=SEVERITY_SLA[vuln["severity"]],
            ))
    
    return findings

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.post("/scan", response_model=ScanResponse)
def scan_dependencies(req: ScanRequest) -> ScanResponse:
    """
    Scan dependencies for known vulnerabilities.
    Implements SEC-2.4 Dependency Vulnerability Response policy.
    """
    log.info("scanning_dependencies", requirements_length=len(req.requirements))
    
    deps = _parse_requirements(req.requirements)
    all_findings: List[VulnerabilityFinding] = []
    
    for pkg, version in deps.items():
        findings = _check_package(pkg, version)
        all_findings.extend(findings)
    
    # Sort by severity (critical first)
    severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
    all_findings.sort(key=lambda f: severity_order[f.severity])
    
    # Calculate summary
    summary = {
        "critical": sum(1 for f in all_findings if f.severity == Severity.CRITICAL),
        "high": sum(1 for f in all_findings if f.severity == Severity.HIGH),
        "medium": sum(1 for f in all_findings if f.severity == Severity.MEDIUM),
        "low": sum(1 for f in all_findings if f.severity == Severity.LOW),
        "total": len(all_findings),
        "packages_scanned": len(deps),
    }
    
    # Policy compliance (SEC-2.4: no unpatched critical/high without ticket)
    policy_compliant = summary["critical"] == 0 and summary["high"] == 0
    
    # Generate recommendations
    recommendations: List[str] = []
    if summary["critical"] > 0:
        recommendations.append("URGENT: Critical vulnerabilities detected - create incident ticket within 24 hours")
    if summary["high"] > 0:
        recommendations.append("HIGH PRIORITY: High severity vulnerabilities must be patched within 72 hours")
    if not policy_compliant:
        recommendations.append("Block merge until critical/high vulnerabilities are resolved")
    if summary["total"] == 0:
        recommendations.append("No known vulnerabilities - proceed with standard review")
    
    # Always recommend version pinning
    if any(v == "unknown" for v in deps.values()):
        recommendations.append("Pin all dependency versions in requirements.txt")
    
    response = ScanResponse(
        findings=all_findings,
        summary=summary,
        policy_compliant=policy_compliant,
        policies_referenced=["SEC-2.4"],
        recommendations=recommendations,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    
    log.info(
        "scan_completed",
        total_findings=len(all_findings),
        critical=summary["critical"],
        high=summary["high"],
        compliant=policy_compliant,
    )
    
    return response


@app.post("/scan-detailed", response_model=ScanResponse)
def scan_detailed(req: DetailedScanRequest) -> ScanResponse:
    """
    Perform detailed vulnerability scan with configurable options.
    """
    log.info("detailed_scan", threshold=req.severity_threshold.value)
    
    deps = _parse_requirements(req.requirements)
    all_findings: List[VulnerabilityFinding] = []
    
    # Filter by severity threshold
    severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
    threshold_level = severity_order[req.severity_threshold]
    
    for pkg, version in deps.items():
        findings = _check_package(pkg, version)
        for f in findings:
            if severity_order[f.severity] <= threshold_level:
                all_findings.append(f)
    
    all_findings.sort(key=lambda f: severity_order[f.severity])
    
    summary = {
        "critical": sum(1 for f in all_findings if f.severity == Severity.CRITICAL),
        "high": sum(1 for f in all_findings if f.severity == Severity.HIGH),
        "medium": sum(1 for f in all_findings if f.severity == Severity.MEDIUM),
        "low": sum(1 for f in all_findings if f.severity == Severity.LOW),
        "total": len(all_findings),
        "packages_scanned": len(deps),
    }
    
    policy_compliant = summary["critical"] == 0 and summary["high"] == 0
    
    recommendations = []
    for f in all_findings:
        if f.severity in [Severity.CRITICAL, Severity.HIGH]:
            recommendations.append(
                f"Upgrade {f.name} from {f.version} to >= {f.fixed_version} ({f.cve})"
            )
    
    return ScanResponse(
        findings=all_findings,
        summary=summary,
        policy_compliant=policy_compliant,
        policies_referenced=["SEC-2.4"],
        recommendations=recommendations[:10],  # Top 10
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/vulnerability/{cve_id}", response_model=CVEDetail)
def get_vulnerability(cve_id: str) -> CVEDetail:
    """
    Get details for a specific CVE.
    """
    log.info("fetching_cve", cve_id=cve_id)
    
    # Search for CVE in our database
    for pkg, vulns in VULNERABILITY_DB.items():
        for vuln in vulns:
            if vuln["cve"] == cve_id:
                return CVEDetail(
                    cve=vuln["cve"],
                    cwe=vuln.get("cwe"),
                    title=vuln["title"],
                    description=vuln["description"],
                    severity=vuln["severity"],
                    cvss_score=vuln["cvss_score"],
                    attack_vector=vuln["attack_vector"],
                    affected_packages=[{"name": pkg, "version_range": vuln["version_range"]}],
                    references=vuln.get("references", []),
                    published_date=vuln["published_date"],
                    last_modified=datetime.now(timezone.utc).isoformat(),
                )
    
    raise HTTPException(status_code=404, detail=f"CVE {cve_id} not found")


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "security-scan-mcp",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/readyz")
def readyz() -> Dict[str, Any]:
    """Readiness check endpoint."""
    return {
        "status": "ready",
        "service": "security-scan-mcp",
        "version": "1.0.0",
        "checks": {
            "vulnerability_db": "loaded",
            "cve_count": sum(len(v) for v in VULNERABILITY_DB.values()),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
