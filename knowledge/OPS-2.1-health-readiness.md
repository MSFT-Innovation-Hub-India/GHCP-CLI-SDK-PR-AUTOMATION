# OPS-2.1 Health & Readiness Endpoints Standard

**Policy ID:** OPS-2.1  
**Category:** Operations  
**Status:** Active  
**Effective Date:** 2024-01-01  
**Last Review:** 2025-06-15  
**Owner:** SRE Team  

---

## 1. Purpose & Scope

### 1.1 Purpose
Define standard health and readiness endpoints for:
- Kubernetes liveness and readiness probes
- Load balancer health checks
- Deployment validation
- Monitoring and alerting

### 1.2 Scope
All HTTP-based services deployed to container orchestration platforms.

---

## 2. Requirements

### 2.1 Endpoint Definitions (MUST)

| Endpoint | Purpose | Probe Type | Response Time |
|----------|---------|------------|---------------|
| `GET /healthz` | Process is alive | Liveness | < 100ms |
| `GET /readyz` | Ready to serve traffic | Readiness | < 500ms |

### 2.2 Health Endpoint (`/healthz`) (MUST)

**Purpose:** Indicate the process is running and not deadlocked.

**Requirements:**
- MUST NOT check external dependencies
- MUST respond with HTTP 200 if process is alive
- MUST respond within 100ms
- SHOULD include basic service metadata

**Response Format:**
```json
{
  "status": "ok",
  "service": "contoso-orders-api",
  "version": "v1.2.3-abc1234",
  "timestamp": "2025-01-15T10:23:45.123Z"
}
```

**Status Codes:**
| Code | Meaning |
|------|---------|
| 200 | Process is healthy |
| 503 | Process is unhealthy (rare - usually process dies) |

### 2.3 Readiness Endpoint (`/readyz`) (MUST)

**Purpose:** Indicate the service is ready to accept traffic.

**Requirements:**
- MUST verify critical dependencies are accessible
- MUST respond with HTTP 200 only when fully ready
- MUST respond within 500ms (use timeouts)
- SHOULD cache dependency checks briefly (1-5 seconds)
- MUST NOT overload dependencies with checks

**Response Format (Healthy):**
```json
{
  "status": "ready",
  "service": "contoso-orders-api", 
  "version": "v1.2.3-abc1234",
  "timestamp": "2025-01-15T10:23:45.123Z",
  "checks": {
    "database": {
      "status": "ok",
      "latency_ms": 12
    },
    "cache": {
      "status": "ok",
      "latency_ms": 3
    },
    "downstream_api": {
      "status": "ok",
      "latency_ms": 45
    }
  }
}
```

**Response Format (Unhealthy):**
```json
{
  "status": "not_ready",
  "service": "contoso-orders-api",
  "version": "v1.2.3-abc1234",
  "timestamp": "2025-01-15T10:23:45.123Z",
  "checks": {
    "database": {
      "status": "ok",
      "latency_ms": 12
    },
    "cache": {
      "status": "failed",
      "error": "Connection refused",
      "latency_ms": 5000
    }
  }
}
```

**Status Codes:**
| Code | Meaning |
|------|---------|
| 200 | Service is ready to accept traffic |
| 503 | Service is not ready (dependencies unavailable) |

---

## 3. Implementation Patterns

### 3.1 FastAPI Implementation

```python
"""
Health & Readiness Endpoints
Implements OPS-2.1 Health & Readiness Endpoints Standard
"""
import asyncio
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI, Response
import structlog

log = structlog.get_logger()

# Service metadata (set at startup)
SERVICE_NAME = "contoso-orders-api"
SERVICE_VERSION = "v1.2.3-abc1234"

# Dependency check timeout
CHECK_TIMEOUT_SECONDS = 2.0

# Simple cache for readiness checks
_readiness_cache: dict[str, Any] = {}
_cache_ttl_seconds = 3.0
_last_check_time = 0.0


app = FastAPI()


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    """
    Liveness probe endpoint.
    Returns 200 if the process is alive.
    Does NOT check external dependencies.
    """
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/readyz")
async def readyz(response: Response) -> dict[str, Any]:
    """
    Readiness probe endpoint.
    Returns 200 only if all critical dependencies are accessible.
    Caches results briefly to avoid overloading dependencies.
    """
    import time
    global _readiness_cache, _last_check_time
    
    now = time.time()
    
    # Return cached result if fresh
    if now - _last_check_time < _cache_ttl_seconds and _readiness_cache:
        result = _readiness_cache.copy()
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        result["cached"] = True
        if result["status"] != "ready":
            response.status_code = 503
        return result
    
    # Perform dependency checks in parallel
    checks = await _check_dependencies()
    
    # Determine overall status
    all_ok = all(c["status"] == "ok" for c in checks.values())
    status = "ready" if all_ok else "not_ready"
    
    if not all_ok:
        response.status_code = 503
        log.warning("readiness_check_failed", checks=checks)
    
    result = {
        "status": status,
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
    
    # Cache the result
    _readiness_cache = result.copy()
    _last_check_time = now
    
    return result


async def _check_dependencies() -> dict[str, dict[str, Any]]:
    """
    Check all critical dependencies in parallel.
    Each check has a timeout to prevent blocking.
    """
    checks = {}
    
    # Run all checks concurrently
    results = await asyncio.gather(
        _check_database(),
        _check_cache(),
        return_exceptions=True,
    )
    
    checks["database"] = results[0] if not isinstance(results[0], Exception) else {
        "status": "failed",
        "error": str(results[0]),
    }
    
    checks["cache"] = results[1] if not isinstance(results[1], Exception) else {
        "status": "failed", 
        "error": str(results[1]),
    }
    
    return checks


async def _check_database() -> dict[str, Any]:
    """Check database connectivity."""
    import time
    start = time.perf_counter()
    
    try:
        # Replace with actual database check
        # Example: await db.execute("SELECT 1")
        await asyncio.wait_for(
            _simulate_db_check(),
            timeout=CHECK_TIMEOUT_SECONDS,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        return {"status": "ok", "latency_ms": round(latency_ms, 1)}
    except asyncio.TimeoutError:
        return {"status": "failed", "error": "Timeout", "latency_ms": CHECK_TIMEOUT_SECONDS * 1000}
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return {"status": "failed", "error": str(e), "latency_ms": round(latency_ms, 1)}


async def _check_cache() -> dict[str, Any]:
    """Check cache connectivity."""
    import time
    start = time.perf_counter()
    
    try:
        # Replace with actual cache check
        # Example: await redis.ping()
        await asyncio.wait_for(
            _simulate_cache_check(),
            timeout=CHECK_TIMEOUT_SECONDS,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        return {"status": "ok", "latency_ms": round(latency_ms, 1)}
    except asyncio.TimeoutError:
        return {"status": "failed", "error": "Timeout", "latency_ms": CHECK_TIMEOUT_SECONDS * 1000}
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return {"status": "failed", "error": str(e), "latency_ms": round(latency_ms, 1)}


async def _simulate_db_check() -> None:
    """Simulate database check (replace with real implementation)."""
    await asyncio.sleep(0.01)  # 10ms simulated latency


async def _simulate_cache_check() -> None:
    """Simulate cache check (replace with real implementation)."""
    await asyncio.sleep(0.003)  # 3ms simulated latency
```

### 3.2 Kubernetes Configuration

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: contoso-orders-api
spec:
  template:
    spec:
      containers:
        - name: api
          image: contoso/orders-api:v1.2.3
          ports:
            - containerPort: 8000
          
          # Liveness probe - restart if unresponsive
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 15
            timeoutSeconds: 3
            failureThreshold: 3
          
          # Readiness probe - remove from LB if not ready
          readinessProbe:
            httpGet:
              path: /readyz
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 2
            successThreshold: 1
```

---

## 4. Testing Requirements (MUST)

### 4.1 Unit Tests

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_healthz_returns_200():
    """Health endpoint must return 200."""
    response = client.get("/healthz")
    assert response.status_code == 200


def test_healthz_response_schema():
    """Health endpoint must return required fields."""
    response = client.get("/healthz")
    data = response.json()
    
    assert "status" in data
    assert "service" in data
    assert "version" in data
    assert "timestamp" in data
    assert data["status"] == "ok"


def test_readyz_returns_200_when_healthy():
    """Readiness endpoint returns 200 when dependencies ok."""
    response = client.get("/readyz")
    assert response.status_code == 200


def test_readyz_response_schema():
    """Readiness endpoint must return required fields."""
    response = client.get("/readyz")
    data = response.json()
    
    assert "status" in data
    assert "service" in data
    assert "checks" in data


def test_readyz_includes_checks():
    """Readiness endpoint must include dependency checks."""
    response = client.get("/readyz")
    data = response.json()
    
    assert "checks" in data
    # At minimum, should check database
    assert len(data["checks"]) >= 1


def test_healthz_response_time():
    """Health endpoint must respond quickly."""
    import time
    start = time.perf_counter()
    client.get("/healthz")
    duration_ms = (time.perf_counter() - start) * 1000
    
    assert duration_ms < 100, f"Health check took {duration_ms}ms, expected < 100ms"
```

---

## 5. Anti-Patterns (MUST NOT)

### 5.1 Checking Dependencies in Liveness
```python
# BAD - Liveness should not check dependencies
@app.get("/healthz")
async def healthz():
    await db.execute("SELECT 1")  # Wrong!
    return {"status": "ok"}
```

### 5.2 No Timeout on Readiness Checks
```python
# BAD - Can hang indefinitely
@app.get("/readyz")
async def readyz():
    await db.execute("SELECT 1")  # No timeout!
    return {"status": "ready"}
```

### 5.3 Heavy Operations in Health Checks
```python
# BAD - Expensive operations in health check
@app.get("/readyz")
async def readyz():
    count = await db.execute("SELECT COUNT(*) FROM large_table")  # Wrong!
    return {"status": "ready", "record_count": count}
```

---

## 6. References

- [Kubernetes Liveness and Readiness Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Health Check Response Format for HTTP APIs (RFC draft)](https://datatracker.ietf.org/doc/html/draft-inadarei-api-health-check)
- [The Twelve-Factor App](https://12factor.net/)
