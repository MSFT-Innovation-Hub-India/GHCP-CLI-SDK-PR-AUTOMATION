# REL-1.0 Pull Request Gates & Quality Bar Standard

**Policy ID:** REL-1.0  
**Category:** Release Engineering  
**Status:** Active  
**Effective Date:** 2024-01-01  
**Last Review:** 2025-06-15  
**Owner:** Platform Engineering  

---

## 1. Purpose & Scope

### 1.1 Purpose
Define mandatory quality gates for all Pull Requests to ensure:
- Consistent code quality across services
- Operational readiness before deployment
- Security baseline compliance
- Reduced production incidents

### 1.2 Scope
All repositories containing deployable code, including:
- APIs and microservices
- Web applications
- Background workers
- Infrastructure as Code

---

## 2. Gate Categories

### 2.1 Gate Levels

| Level | Description | Blocking |
|-------|-------------|----------|
| **L0 - Build** | Code compiles/installs | ✅ Blocks merge |
| **L1 - Test** | Unit tests pass | ✅ Blocks merge |
| **L2 - Quality** | Lint, format, coverage | ✅ Blocks merge |
| **L3 - Security** | Vulnerability scan | ✅ Blocks merge (Critical/High) |
| **L4 - Compliance** | Policy checks | ✅ Blocks merge |
| **L5 - Review** | Human approval | ✅ Blocks merge |

---

## 3. Mandatory Gates (MUST)

### 3.1 L0 - Build Gate

**Requirement:** Code must build/install successfully.

```yaml
# Example: Python
- name: Install dependencies
  run: pip install -r requirements.txt

- name: Verify imports
  run: python -c "import app.main"
```

**Validation:**
- [ ] All dependencies resolve
- [ ] No import errors
- [ ] Docker build succeeds (if applicable)

### 3.2 L1 - Test Gate

**Requirement:** All unit tests must pass.

```yaml
- name: Run tests
  run: |
    pytest tests/ \
      --tb=short \
      --junitxml=test-results.xml \
      -v
```

**Validation:**
- [ ] All tests pass (100% pass rate)
- [ ] No skipped tests without justification
- [ ] Test execution completes within timeout

### 3.3 L2 - Quality Gate

**Requirement:** Code meets quality standards.

| Check | Tool | Threshold |
|-------|------|-----------|
| Linting | ruff, flake8 | 0 errors |
| Formatting | black, prettier | 0 differences |
| Type checking | mypy, pyright | 0 errors |
| Code coverage | pytest-cov | ≥ 80% (new code) |
| Complexity | radon | ≤ 10 (cyclomatic) |

```yaml
- name: Lint
  run: ruff check .

- name: Format check
  run: black --check .

- name: Type check
  run: mypy app/

- name: Coverage
  run: |
    pytest --cov=app --cov-fail-under=80 tests/
```

### 3.4 L3 - Security Gate

**Requirement:** No Critical/High vulnerabilities.

```yaml
- name: Dependency scan
  run: |
    pip-audit --strict
    safety check

- name: SAST scan
  run: bandit -r app/ -ll

- name: Secret detection
  run: detect-secrets scan --baseline .secrets.baseline
```

**Validation:**
- [ ] No Critical vulnerabilities (blocks merge)
- [ ] No High vulnerabilities (blocks merge)
- [ ] No hardcoded secrets detected
- [ ] SAST findings reviewed

### 3.5 L4 - Compliance Gate

**Requirement:** Service meets operational standards.

| Policy | Check | Reference |
|--------|-------|-----------|
| Health endpoints | `/healthz` exists | OPS-2.1 |
| Readiness endpoints | `/readyz` exists | OPS-2.1 |
| Structured logging | structlog configured | OBS-1.1 |
| Correlation IDs | Middleware present | OBS-3.2 |
| Documentation | README.md present | DOC-1.0 |

```yaml
- name: Check health endpoint
  run: |
    grep -r "/healthz" app/ || (echo "Missing /healthz endpoint" && exit 1)

- name: Check readiness endpoint
  run: |
    grep -r "/readyz" app/ || (echo "Missing /readyz endpoint" && exit 1)

- name: Check structured logging
  run: |
    grep -r "structlog" app/ || (echo "Missing structured logging" && exit 1)

- name: Check correlation middleware
  run: |
    grep -r "RequestContextMiddleware\|trace_id" app/ || \
      (echo "Missing correlation middleware" && exit 1)
```

### 3.6 L5 - Review Gate

**Requirement:** Human approval based on CM-7 matrix.

| Change Type | Required Approvals |
|-------------|-------------------|
| Standard | 1 ServiceOwner |
| High-impact service | 1 SRE + 1 ServiceOwner |
| Security-sensitive | 1 Security + 1 ServiceOwner |
| Infrastructure | 1 SRE |
| Database | 1 DBA |

---

## 4. Implementation

### 4.1 GitHub Actions Workflow

```yaml
# .github/workflows/pr-gates.yml
name: PR Gates

on:
  pull_request:
    branches: [main, develop]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # L0: Build
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Verify imports
        run: python -c "from app.main import app"

  # L1: Tests
  test:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest tests/ \
            --tb=short \
            --junitxml=test-results.xml \
            --cov=app \
            --cov-report=xml \
            --cov-fail-under=80
      - uses: codecov/codecov-action@v4
        with:
          files: coverage.xml

  # L2: Quality
  quality:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install tools
        run: pip install ruff black mypy
      - name: Lint
        run: ruff check .
      - name: Format
        run: black --check .
      - name: Type check
        run: mypy app/ --ignore-missing-imports

  # L3: Security
  security:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Install security tools
        run: pip install pip-audit bandit safety
      - name: Dependency scan
        run: pip-audit --strict
      - name: SAST scan
        run: bandit -r app/ -ll -ii
      - name: Secret detection
        uses: trufflesecurity/trufflehog@main
        with:
          extra_args: --only-verified

  # L4: Compliance
  compliance:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check health endpoint
        run: |
          if ! grep -rq '"/healthz"' app/; then
            echo "::error::Missing /healthz endpoint (OPS-2.1)"
            exit 1
          fi
      - name: Check readiness endpoint
        run: |
          if ! grep -rq '"/readyz"' app/; then
            echo "::error::Missing /readyz endpoint (OPS-2.1)"
            exit 1
          fi
      - name: Check structured logging
        run: |
          if ! grep -rq 'structlog' app/; then
            echo "::error::Missing structured logging (OBS-1.1)"
            exit 1
          fi
      - name: Check correlation middleware
        run: |
          if ! grep -rqE 'trace_id|RequestContextMiddleware' app/; then
            echo "::error::Missing correlation middleware (OBS-3.2)"
            exit 1
          fi
      - name: Check README exists
        run: test -f README.md

  # Summary
  gates-passed:
    needs: [build, test, quality, security, compliance]
    runs-on: ubuntu-latest
    steps:
      - name: All gates passed
        run: echo "✅ All PR gates passed!"
```

### 4.2 Branch Protection Rules

Configure in GitHub repository settings:

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "build",
      "test",
      "quality",
      "security",
      "compliance"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

---

## 5. Test Requirements

### 5.1 Minimum Test Coverage

```python
# tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Tests for OPS-2.1 compliance."""
    
    def test_healthz_returns_200(self):
        """Health endpoint must return 200 when alive."""
        response = client.get("/healthz")
        assert response.status_code == 200
    
    def test_healthz_returns_json(self):
        """Health endpoint must return JSON."""
        response = client.get("/healthz")
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert "status" in data
        assert "service" in data
    
    def test_readyz_returns_200(self):
        """Readiness endpoint must return 200 when ready."""
        response = client.get("/readyz")
        assert response.status_code == 200
    
    def test_readyz_includes_checks(self):
        """Readiness endpoint must include dependency checks."""
        response = client.get("/readyz")
        data = response.json()
        assert "checks" in data or "status" in data


class TestCorrelation:
    """Tests for OBS-3.2 compliance."""
    
    def test_response_includes_trace_id(self):
        """Response must include x-trace-id header."""
        response = client.get("/healthz")
        assert "x-trace-id" in response.headers
    
    def test_response_includes_request_id(self):
        """Response must include x-request-id header."""
        response = client.get("/healthz")
        assert "x-request-id" in response.headers
    
    def test_trace_id_propagated(self):
        """Inbound trace_id must be preserved."""
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        headers = {"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"}
        response = client.get("/healthz", headers=headers)
        assert response.headers["x-trace-id"] == trace_id
```

### 5.2 Coverage Enforcement

```python
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=app --cov-fail-under=80 --cov-report=term-missing"

[tool.coverage.run]
branch = true
source = ["app"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

---

## 6. Agent Enforcement

### 6.1 What Fleet Agents Enforce

| Gate | Agent Action |
|------|--------------|
| Health endpoints | Add if missing |
| Readiness endpoints | Add if missing |
| Structured logging | Configure if missing |
| Correlation middleware | Add if missing |
| Test coverage | Add test files |
| Vulnerability fixes | Upgrade packages |

### 6.2 What Requires Human Review

| Gate | Human Action |
|------|--------------|
| Business logic changes | Code review |
| API changes | Contract review |
| Security findings | Risk assessment |
| Final approval | Merge decision |

---

## 7. Exceptions

### 7.1 Waiver Process
If a gate cannot be satisfied:

1. Document justification in PR description
2. Request waiver from Platform Engineering
3. Add `gate-waiver` label with reason
4. Schedule remediation timeline

### 7.2 Valid Waiver Reasons
- Emergency hotfix (post-incident remediation required)
- Third-party limitation (documented workaround)
- Deprecation in progress (removal scheduled)

---

## 8. References

- [OBS-1.1 Structured Logging Standard](./OBS-1.1-structured-logging.md)
- [OBS-3.2 Trace & Correlation Propagation](./OBS-3.2-trace-propagation.md)
- [OPS-2.1 Health & Readiness Endpoints](./OPS-2.1-health-readiness.md)
- [CM-7 Change Management Approval Matrix](./CM-7-approval-matrix.md)
- [SEC-2.4 Dependency Vulnerability Response](./SEC-2.4-dependency-vulnerability-response.md)
