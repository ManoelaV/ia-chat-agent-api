from fastapi.testclient import TestClient
import os
import importlib.util
import sys
from pathlib import Path

# The test harness will respect `MOCK_AGENT` if set in the environment or
# in a local `.env`. We do NOT force mocking here so tests can run end-to-end
# when you configure a real LLM/SDK (for local dev, set MOCK_AGENT=true).

# Dynamically load app.main to avoid package import issues in test runner
root = Path(__file__).resolve().parents[1]
main_path = root / "app" / "main.py"
spec = importlib.util.spec_from_file_location("app.main", str(main_path))
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load app module from {main_path}")
app_main = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(root))
sys.modules[spec.name] = app_main
spec.loader.exec_module(app_main)

app = getattr(app_main, "app")

tests = [
    {"message": "Qual é a capital da França?"},
    {"message": "Quanto é 1234 * 5678?"},
]

with TestClient(app) as client:
    for t in tests:
        resp = client.post("/chat", json=t)
        print("Request:", t)
        try:
            print("Status:", resp.status_code)
            print("JSON:", resp.json())
        except Exception as e:
            print("Erro ao ler resposta:", e)
        print("---")
