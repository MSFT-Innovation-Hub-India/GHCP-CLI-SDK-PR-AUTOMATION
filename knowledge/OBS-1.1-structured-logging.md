# OBS-1.1 Structured Logging Standard

**Policy ID:** OBS-1.1  
**Category:** Observability  
**Status:** Active  
**Effective Date:** 2024-01-01  
**Last Review:** 2025-06-15  
**Owner:** Platform Engineering  

---

## 1. Purpose & Scope

### 1.1 Purpose
This standard establishes requirements for structured logging across all production services to ensure operational visibility, security auditability, and efficient incident response.

### 1.2 Scope
- All production services (APIs, workers, scheduled jobs, async processors)
- All environments: development, staging, production
- All programming languages and frameworks

### 1.3 Out of Scope
- Browser/client-side logging (covered by OBS-1.2)
- Application Performance Monitoring traces (covered by OBS-3.x)

---

## 2. Requirements

### 2.1 Log Format (MUST)

All logs in production environments MUST be structured JSON. Plain text logs are prohibited in production.

```json
{
  "timestamp": "2025-01-15T10:23:45.123Z",
  "level": "INFO",
  "service": {
    "name": "contoso-orders-api",
    "version": "v1.2.3-abc1234",
    "environment": "production",
    "instance_id": "orders-api-7d4f5-xk2j9"
  },
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "request_id": "req-uuid-1234-5678",
  "event": "order.created",
  "message": "Order created successfully",
  "context": {
    "order_id": "ORD-12345",
    "customer_tier": "premium",
    "items_count": 3
  },
  "duration_ms": 145
}
```

### 2.2 Required Fields (MUST)

Every log record MUST include:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `timestamp` | ISO-8601 UTC | Event occurrence time | `2025-01-15T10:23:45.123Z` |
| `level` | Enum | Severity level | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `service.name` | String | Service identifier | `contoso-orders-api` |
| `service.version` | String | Build SHA or semver | `v1.2.3-abc1234` |
| `service.environment` | Enum | Deployment environment | `dev`, `staging`, `prod` |
| `trace_id` | String(32) | W3C trace correlation ID | `4bf92f3577b34da6a3ce929d0e0e4736` |
| `request_id` | UUID | Per-request correlation | `req-uuid-1234-5678` |
| `event` | String | Stable event identifier | `order.created`, `auth.failed` |
| `message` | String | Human-readable description | `Order created successfully` |

### 2.3 Error Logging (MUST)

Error and exception logs MUST include:

```json
{
  "level": "ERROR",
  "event": "payment.failed",
  "message": "Payment processing failed",
  "error": {
    "type": "PaymentGatewayTimeout",
    "message": "Connection to payment provider timed out after 30s",
    "code": "PAYMENT_TIMEOUT_001",
    "stack": "Traceback (most recent call last):\n  File \"payment.py\", line 45...",
    "cause": "socket.timeout"
  },
  "context": {
    "payment_id": "PAY-789",
    "gateway": "stripe",
    "retry_count": 2
  }
}
```

### 2.4 Sensitive Data Handling (MUST NOT)

**Never log:**
- Passwords, API keys, tokens, secrets
- Credit card numbers (even partial)
- Social Security Numbers or government IDs
- Personal health information (PHI)
- Full email addresses in most contexts

**Masking requirements:**
- Mask to last 4 characters: `****5678`
- Or use reference IDs: `user_ref: usr_abc123`

### 2.5 Log Levels (RECOMMENDED)

| Level | Use When |
|-------|----------|
| `DEBUG` | Detailed diagnostic info (disabled in prod by default) |
| `INFO` | Normal operational events |
| `WARNING` | Unexpected but handled situations |
| `ERROR` | Failures requiring attention |
| `CRITICAL` | System-wide failures, immediate action required |

---

## 3. Implementation Patterns

### 3.1 Python with structlog

```python
import logging
import structlog
from app.middleware import get_trace_id, get_request_id

# Configure structlog
def configure_logging(service_name: str, version: str, environment: str) -> None:
    """Configure structured logging for the service."""
    
    # Add context processor for correlation IDs
    def add_correlation_ids(logger, method_name, event_dict):
        event_dict["trace_id"] = get_trace_id()
        event_dict["request_id"] = get_request_id()
        return event_dict
    
    # Add service context
    def add_service_context(logger, method_name, event_dict):
        event_dict["service"] = {
            "name": service_name,
            "version": version,
            "environment": environment,
        }
        return event_dict
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_correlation_ids,
            add_service_context,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Usage
log = structlog.get_logger()

def process_order(order_id: str, items: list) -> None:
    log.info(
        "order.processing_started",
        order_id=order_id,
        items_count=len(items)
    )
    try:
        # Process order...
        log.info("order.processing_completed", order_id=order_id, duration_ms=145)
    except Exception as e:
        log.error(
            "order.processing_failed",
            order_id=order_id,
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True
        )
        raise
```

### 3.2 HTTP Request/Response Logging

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
import time

log = structlog.get_logger()

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        # Log request start (optional, can be verbose)
        log.debug(
            "http.request_started",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params),
        )
        
        response = await call_next(request)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Log request completion (always)
        log.info(
            "http.request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        
        return response
```

---

## 4. Anti-Patterns (MUST NOT)

### 4.1 String Interpolation
```python
# BAD - Unstructured, hard to query
log.info(f"User {user_id} placed order {order_id} for ${amount}")

# GOOD - Structured, queryable
log.info("order.placed", user_id=user_id, order_id=order_id, amount=amount)
```

### 4.2 Sensitive Data Exposure
```python
# BAD - Exposes credentials
log.info("auth.attempt", username=username, password=password)

# GOOD - No sensitive data
log.info("auth.attempt", username=username, ip_address=ip)
```

### 4.3 High-Cardinality Abuse
```python
# BAD - Full request body creates unbounded cardinality
log.info("request.received", body=request.body)

# GOOD - Log summary metrics
log.info("request.received", content_length=len(request.body), content_type=content_type)
```

---

## 5. Validation & Compliance

### 5.1 CI/CD Validation

CI pipelines SHOULD validate:
- [ ] Logger is configured (structlog import present)
- [ ] No `print()` statements in production code
- [ ] Correlation ID middleware is registered
- [ ] No sensitive data patterns detected in log statements

### 5.2 Runtime Validation

Production deployments SHOULD verify:
- Logs are JSON-parseable
- Required fields are present
- Correlation IDs propagate end-to-end

---

## 6. References

- [OBS-3.2 Trace & Correlation Propagation](./OBS-3.2-trace-propagation.md)
- [SEC-4.1 Sensitive Data Handling](./SEC-4.1-sensitive-data.md)
- [OpenTelemetry Logging Specification](https://opentelemetry.io/docs/specs/otel/logs/)
- [12-Factor App: Logs](https://12factor.net/logs)
