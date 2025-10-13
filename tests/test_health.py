import requests
import time
import subprocess
import os

CORE = "http://localhost:8002"  # Bootstrap core API (configured in .env)
REAL = "http://localhost:8001"  # Bootstrap realtime API

def wait(port):
    for _ in range(50):
        try:
            requests.get(f"http://localhost:{port}/health", timeout=0.5)
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"service on {port} not responding")

def test_health_endpoints():
    # assumes you already started both services in separate terminals
    wait(8002)
    wait(8001)

    r1 = requests.get(f"{CORE}/health", timeout=1).json()
    r2 = requests.get(f"{REAL}/health", timeout=1).json()
    assert r1["status"] == "ok" and r1["service"] == "core"
    assert r2["status"] == "ok" and r2["service"] == "realtime"

def test_version_endpoints():
    v1 = requests.get(f"{CORE}/version", timeout=1).json()
    v2 = requests.get(f"{REAL}/version", timeout=1).json()
    assert "name" in v1 and "version" in v1
    assert "name" in v2 and "version" in v2
