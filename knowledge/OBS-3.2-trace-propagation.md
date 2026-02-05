# OBS-3.2 Trace & Correlation Propagation Standard

**Policy ID:** OBS-3.2  
**Category:** Observability  
**Status:** Active  
**Effective Date:** 2024-01-01  
**Last Review:** 2025-06-15  
**Owner:** Platform Engineering  

---

## 1. Purpose & Scope

### 1.1 Purpose
Enable end-to-end request correlation across distributed services, supporting:
- Distributed tracing for performance analysis
- Log correlation for debugging
- Cross-service error tracking
- Request flow visualization

### 1.2 Scope
- All HTTP/gRPC services (APIs, gateways, BFFs)
- Message queue consumers and producers
- Background job processors
- External service integrations

---

## 2. Requirements

### 2.1 Inbound Header Processing (MUST)

Services MUST accept and parse the W3C `traceparent` header:

**Format:** `{version}-{trace_id}-{span_id}-{flags}`

**Example:** `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`

| Field | Length | Description |
|-------|--------|-------------|
| version | 2 chars | Always `00` for current spec |
| trace_id | 32 chars | Unique trace identifier (hex) |
| span_id | 16 chars | Parent span identifier (hex) |
| flags | 2 chars | Trace flags (`01` = sampled) |

### 2.2 ID Generation (MUST)

When inbound `traceparent` is absent or malformed:
- Generate a new 32-character hex `trace_id`
- Use cryptographically random source (not sequential)

When `x-request-id` header is absent:
- Generate a new UUID v4 `request_id`

### 2.3 Response Headers (MUST)

Services MUST return correlation headers:

| Header | Description |
|--------|-------------|
| `x-trace-id` | The trace_id used for this request |
| `x-request-id` | The request correlation ID |

### 2.4 Downstream Propagation (MUST)

When calling downstream services:
- Propagate `traceparent` with new span_id
- Propagate `x-request-id` unchanged
- Include `tracestate` if present (vendor extensions)

### 2.5 Logging Integration (MUST)

All log records MUST include `trace_id` and `request_id` fields (see OBS-1.1).

---

## 3. Implementation Patterns

### 3.1 FastAPI Middleware (Python)

```python
"""
Request Context Middleware
Implements OBS-3.2 Trace & Correlation Propagation
"""
import contextvars
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variables for correlation IDs
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("span_id", default="")
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

def get_trace_id() -> str:
    """Get current trace_id from context."""
    return trace_id_var.get() or ""

def get_span_id() -> str:
    """Get current span_id from context."""
    return span_id_var.get() or ""

def get_request_id() -> str:
    """Get current request_id from context."""
    return request_id_var.get() or ""

def generate_trace_id() -> str:
    """Generate a new 32-character trace ID."""
    return uuid.uuid4().hex

def generate_span_id() -> str:
    """Generate a new 16-character span ID."""
    return uuid.uuid4().hex[:16]

def parse_traceparent(traceparent: str) -> tuple[str, str] | None:
    """
    Parse W3C traceparent header.
    Returns (trace_id, parent_span_id) or None if invalid.
    
    Format: {version}-{trace_id}-{span_id}-{flags}
    Example: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
    """
    if not traceparent:
        return None
    
    try:
        parts = traceparent.split("-")
        if len(parts) != 4:
            return None
        
        version, trace_id, span_id, flags = parts
        
        # Validate version
        if version != "00":
            return None
        
        # Validate trace_id (32 hex chars, not all zeros)
        if len(trace_id) != 32 or not all(c in "0123456789abcdef" for c in trace_id.lower()):
            return None
        if trace_id == "0" * 32:
            return None
        
        # Validate span_id (16 hex chars, not all zeros)
        if len(span_id) != 16 or not all(c in "0123456789abcdef" for c in span_id.lower()):
            return None
        if span_id == "0" * 16:
            return None
        
        return trace_id.lower(), span_id.lower()
    except Exception:
        return None

def build_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    """Build W3C traceparent header value."""
    flags = "01" if sampled else "00"
    return f"00-{trace_id}-{span_id}-{flags}"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware implementing OBS-3.2 trace correlation.
    
    - Extracts trace_id from inbound traceparent header
    - Generates new trace_id if absent/malformed
    - Propagates x-request-id or generates new one
    - Sets response headers for correlation
    - Stores IDs in contextvars for logging integration
    """
    
    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate trace context
        traceparent = request.headers.get("traceparent", "")
        parsed = parse_traceparent(traceparent)
        
        if parsed:
            trace_id, parent_span_id = parsed
        else:
            trace_id = generate_trace_id()
            parent_span_id = None
        
        # Generate new span for this service
        span_id = generate_span_id()
        
        # Extract or generate request_id
        request_id = request.headers.get("x-request-id", "") or str(uuid.uuid4())
        
        # Set context variables for logging
        trace_id_var.set(trace_id)
        span_id_var.set(span_id)
        request_id_var.set(request_id)
        
        # Process request
        response: Response = await call_next(request)
        
        # Set response headers
        response.headers["x-trace-id"] = trace_id
        response.headers["x-request-id"] = request_id
        response.headers["x-span-id"] = span_id
        
        return response


def get_outbound_headers() -> dict[str, str]:
    """
    Get headers to propagate to downstream services.
    Call this when making HTTP requests to other services.
    """
    trace_id = get_trace_id()
    request_id = get_request_id()
    
    # Generate new span for downstream call
    new_span_id = generate_span_id()
    
    headers = {
        "x-request-id": request_id,
    }
    
    if trace_id:
        headers["traceparent"] = build_traceparent(trace_id, new_span_id)
    
    return headers
```

### 3.2 HTTP Client Integration

```python
import httpx
from app.middleware import get_outbound_headers

async def call_downstream_service(url: str, payload: dict) -> dict:
    """Call downstream service with trace propagation."""
    headers = get_outbound_headers()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
```

### 3.3 Message Queue Integration

```python
import json
from app.middleware import get_trace_id, get_request_id, trace_id_var, request_id_var

def publish_message(queue: str, payload: dict) -> None:
    """Publish message with trace context in headers."""
    message = {
        "payload": payload,
        "metadata": {
            "trace_id": get_trace_id(),
            "request_id": get_request_id(),
            "timestamp": datetime.utcnow().isoformat(),
        }
    }
    # Publish to queue...

def process_message(message: dict) -> None:
    """Process message, restoring trace context."""
    metadata = message.get("metadata", {})
    
    # Restore context for logging
    trace_id_var.set(metadata.get("trace_id", generate_trace_id()))
    request_id_var.set(metadata.get("request_id", str(uuid.uuid4())))
    
    # Process payload...
```

---

## 4. Anti-Patterns (MUST NOT)

### 4.1 Generating New Trace ID Per Call
```python
# BAD - Breaks correlation chain
async def call_service(url):
    response = await client.get(url, headers={
        "traceparent": f"00-{uuid.uuid4().hex}-{uuid.uuid4().hex[:16]}-01"  # Wrong!
    })
```

### 4.2 Not Propagating Context
```python
# BAD - Downstream correlation lost
async def call_service(url):
    response = await client.get(url)  # No headers propagated!
```

### 4.3 Logging Only at Request Start
```python
# BAD - Missing correlation in business logic
@app.post("/orders")
async def create_order(order: Order):
    log.info("request received", trace_id=get_trace_id())  # Only here
    result = process_order(order)  # No logging inside
    return result
```

---

## 5. Validation

### 5.1 Integration Tests

```python
def test_trace_propagation():
    """Verify trace ID propagates through request."""
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    headers = {"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"}
    
    response = client.get("/healthz", headers=headers)
    
    assert response.headers["x-trace-id"] == trace_id
    assert "x-request-id" in response.headers

def test_trace_generation():
    """Verify trace ID generated when not provided."""
    response = client.get("/healthz")  # No traceparent
    
    assert "x-trace-id" in response.headers
    assert len(response.headers["x-trace-id"]) == 32
```

### 5.2 CI Validation

- [ ] RequestContextMiddleware registered in app startup
- [ ] get_outbound_headers() used in HTTP clients
- [ ] Log records include trace_id field

---

## 6. References

- [W3C Trace Context Specification](https://www.w3.org/TR/trace-context/)
- [OpenTelemetry Propagation](https://opentelemetry.io/docs/concepts/context-propagation/)
- [OBS-1.1 Structured Logging Standard](./OBS-1.1-structured-logging.md)
