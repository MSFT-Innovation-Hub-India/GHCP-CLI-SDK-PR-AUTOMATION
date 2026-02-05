from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Drift:
    applicable: bool
    missing_healthz: bool = False
    missing_readyz: bool = False
    missing_structlog: bool = False
    missing_middleware: bool = False

def detect(repo: Path) -> Drift:
    main_py = repo / "app" / "main.py"
    if not main_py.exists():
        return Drift(applicable=False)
    txt = main_py.read_text(encoding="utf-8")
    return Drift(
        applicable=True,
        missing_healthz="/healthz" not in txt,
        missing_readyz="/readyz" not in txt,
        missing_structlog="structlog" not in txt,
        missing_middleware="RequestContextMiddleware" not in txt,
    )

def apply(repo: Path, service_name: str) -> list[str]:
    touched: list[str] = []

    req = repo / "requirements.txt"
    if req.exists():
        r = req.read_text(encoding="utf-8")
        if "structlog" not in r.lower():
            req.write_text(r.rstrip() + "\nstructlog==24.2.0\n", encoding="utf-8")
            touched.append("requirements.txt")

    (repo / "app").mkdir(parents=True, exist_ok=True)

    mw = repo / "app" / "middleware.py"
    if not mw.exists():
        mw.write_text(_middleware_py(), encoding="utf-8")
        touched.append("app/middleware.py")

    lc = repo / "app" / "logging_config.py"
    if not lc.exists():
        lc.write_text(_logging_py(service_name), encoding="utf-8")
        touched.append("app/logging_config.py")

    main_py = repo / "app" / "main.py"
    m = main_py.read_text(encoding="utf-8")

    if "from app.logging_config import configure_logging" not in m:
        m = "from app.logging_config import configure_logging\n" + m
        touched.append("app/main.py")
    if "from app.middleware import RequestContextMiddleware" not in m:
        m = "from app.middleware import RequestContextMiddleware\n" + m
        touched.append("app/main.py")

    if "configure_logging()" not in m:
        lines = m.splitlines()
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip() and not (line.startswith("import ") or line.startswith("from ")):
                insert_at = i
                break
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, "configure_logging()")
        lines.insert(insert_at + 2, "")
        m = "\n".join(lines)
        touched.append("app/main.py")

    if "app.add_middleware(RequestContextMiddleware" not in m:
        out = []
        added = False
        in_fastapi_def = False
        paren_depth = 0
        for line in m.splitlines():
            out.append(line)
            if not added:
                # Track if we're in a multi-line FastAPI() definition
                if line.strip().startswith("app = FastAPI"):
                    in_fastapi_def = True
                    paren_depth = line.count("(") - line.count(")")
                    # If single line (balanced parens), add middleware now
                    if paren_depth == 0:
                        out.append("")
                        out.append("# Correlation middleware (trace_id/request_id)")
                        out.append(f'app.add_middleware(RequestContextMiddleware, service_name="{service_name}")')
                        added = True
                elif in_fastapi_def:
                    paren_depth += line.count("(") - line.count(")")
                    # When parens balance, the definition is complete
                    if paren_depth <= 0:
                        out.append("")
                        out.append("# Correlation middleware (trace_id/request_id)")
                        out.append(f'app.add_middleware(RequestContextMiddleware, service_name="{service_name}")')
                        added = True
                        in_fastapi_def = False
        m = "\n".join(out)
        touched.append("app/main.py")

    if "/healthz" not in m:
        m += (
            f'\n\n@app.get("/healthz")\n'
            f'def healthz():\n'
            f'    return {{"status":"ok","service":"{service_name}","version":"dev","timestamp":"now"}}\n'
        )
        touched.append("app/main.py")

    if "/readyz" not in m:
        m += (
            f'\n\n@app.get("/readyz")\n'
            f'def readyz():\n'
            f'    return {{"status":"ready","service":"{service_name}","version":"dev","timestamp":"now"}}\n'
        )
        touched.append("app/main.py")

    main_py.write_text(m + ("\n" if not m.endswith("\n") else ""), encoding="utf-8")

    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    th = tests_dir / "test_health.py"
    if not th.exists():
        th.write_text(_tests_py(), encoding="utf-8")
        touched.append("tests/test_health.py")

    return sorted(set(touched))

def _middleware_py() -> str:
    return '''import contextvars
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

trace_id_var = contextvars.ContextVar("trace_id", default="")
request_id_var = contextvars.ContextVar("request_id", default="")

def get_trace_id() -> str:
    return trace_id_var.get() or ""

def get_request_id() -> str:
    return request_id_var.get() or ""

def _extract_trace_id(traceparent: str) -> str:
    # W3C traceparent: 00-<trace_id>-<span_id>-<flags>
    try:
        parts = traceparent.split("-")
        if len(parts) >= 4 and len(parts[1]) == 32:
            return parts[1]
    except Exception:
        pass
    return ""

class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        tp = request.headers.get("traceparent", "")
        trace_id = _extract_trace_id(tp) or uuid.uuid4().hex
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        trace_id_var.set(trace_id)
        request_id_var.set(req_id)

        response: Response = await call_next(request)
        response.headers["x-trace-id"] = trace_id
        response.headers["x-request-id"] = req_id
        return response
'''

def _logging_py(service_name: str) -> str:
    return f'''import logging
import structlog
from app.middleware import get_trace_id, get_request_id

class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        record.request_id = get_request_id()
        record.service = "{service_name}"
        return True

def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    root = logging.getLogger()
    root.addFilter(_ContextFilter())

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
'''

def _tests_py() -> str:
    return '''from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200

def test_readyz_ok():
    r = client.get("/readyz")
    assert r.status_code == 200

def test_headers_present():
    r = client.get("/healthz")
    assert "x-request-id" in {k.lower(): v for k, v in r.headers.items()}
    assert "x-trace-id" in {k.lower(): v for k, v in r.headers.items()}
'''
