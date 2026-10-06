import json

import pytest

from nutribuddy.cli import main


def test_cli_demo_runs_offline(tmp_path, capsys):
    assert main(["--work-dir", str(tmp_path), "demo"]) == 0
    out = capsys.readouterr().out
    assert "status=possible_condition condition=diabetes" in out
    assert "Sources:" in out and "[ask]" in out


def test_cli_commands_end_to_end(tmp_path, capsys):
    data, work = tmp_path / "data", tmp_path / "work"
    base = ["--data-dir", str(data), "--work-dir", str(work)]
    assert main(["synth", "--out", str(data)]) == 0
    assert main(base + ["load-foods", "--fdc-dir", str(data / "food_data")]) == 0
    assert main(base + ["index"]) == 0
    capsys.readouterr()
    assert main(base + ["plan", "heart", "--json"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["condition"] == "heart" and plan["sources"]
    assert main(base + ["session", "--condition", "thyroid"]) == 0
    sid = capsys.readouterr().out.strip()
    assert main(base + ["ask", sid, "Which foods give iodine?", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "answered"
    assert main(base + ["screen", "I always feel cold and my hair is thinning", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["condition"] == "thyroid"
    assert main(base + ["eval", "--out", str(tmp_path / "r.json")]) == 0
    assert (tmp_path / "r.json").exists()


def test_cli_reports_errors_without_traceback(tmp_path, capsys):
    assert main(["--work-dir", str(tmp_path / "none"), "plan", "heart"]) == 2
    assert "nutribuddy index" in capsys.readouterr().err
    assert main(["--data-dir", str(tmp_path / "nodata"), "--work-dir", str(tmp_path), "index"]) == 2


def test_api_endpoints(workspace):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from nutribuddy.api import PAGE, create_app
    from nutribuddy.service import NutriBuddy

    assert "innerHTML" not in PAGE and "textContent" in PAGE
    client = TestClient(create_app(NutriBuddy.from_settings(workspace)))
    sid = client.post("/api/session", json={"condition": "diabetes"}).json()["session_id"]
    plan = client.post("/api/plan", json={"condition": "diabetes", "session_id": sid}).json()
    assert plan["sources"] and "text" in plan
    ans = client.post("/api/ask", json={"session_id": sid, "question": "Which drinks raise blood glucose?"})
    assert ans.status_code == 200
    assert client.post("/api/ask", json={"session_id": "nope", "question": "rice?"}).status_code == 404
    assert client.post("/api/plan", json={"condition": "asthma"}).status_code == 422
    assert client.post("/api/screen", json={"symptoms": "I fainted"}).json()["status"] == "urgent"
