from __future__ import annotations
import requests

CHANGE_MGMT_URL = "http://localhost:4101/approval"
SECURITY_URL = "http://localhost:4102/scan"

def approval(service: str, touched_paths: list[str]) -> dict:
    r = requests.post(CHANGE_MGMT_URL, json={"service": service, "touched_paths": touched_paths}, timeout=20)
    r.raise_for_status()
    return r.json()

def security_scan(requirements_text: str) -> dict:
    r = requests.post(SECURITY_URL, json={"requirements": requirements_text}, timeout=20)
    r.raise_for_status()
    return r.json()
