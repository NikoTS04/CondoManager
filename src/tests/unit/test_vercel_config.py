import json
from pathlib import Path


def test_services_routing_y_binding_confirmados():
    root = Path(__file__).resolve().parents[3]
    config = json.loads((root / "vercel.json").read_text())
    assert not {"framework", "functions", "buildCommand"} & config.keys()
    assert set(config["services"]) == {"app", "frontend"}
    assert config["services"]["app"]["root"] == "."
    assert config["services"]["frontend"]["root"] == "frontend"
    assert config["services"]["frontend"]["bindings"] == [
        {"type": "service", "service": "app", "format": "url", "env": "APP_URL"}
    ]
    assert config["rewrites"] == [
        {"source": "/api/v1/jobs/diario", "destination": {"service": "app"}},
        {"source": "/(.*)", "destination": {"service": "frontend"}},
    ]
    assert config["crons"] == [
        {"path": "/api/v1/jobs/diario", "schedule": "15 5 * * *"}
    ]
