"""JevJudge direct backend against a fake Jev-compatible server (the OpenJev path)."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.jev import JevJudge

SEEN: list[dict] = []


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        reply = {"model": "openjev-test", "answers": {
            "route": {"type": "choice", "choice": "route_strong",
                      "probabilities": {"route_easy": 0.3, "route_strong": 0.7},
                      "confidence": 0.55}},
            "usage": {"input_tokens": 50, "output_tokens": 5}}
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/v1/systemone"
    srv.shutdown()


def test_direct_backend_speaks_the_documented_wire_format(server, monkeypatch):
    monkeypatch.setenv("JEV_BACKEND", "typesafe")
    monkeypatch.setenv("JEV_ENDPOINT", server)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_MODEL", raising=False)
    SEEN.clear()
    j = JevJudge()
    assert j.name == "jev-compatible" and j.model == "jev-latest"
    q = Question(name="route", type=QuestionType.CHOICE, instructions="route it",
                 options=["route_easy", "route_strong"],
                 descriptions={"route_strong": "frontier model"})
    (out,) = j.decide("task", [q])

    sent = SEEN[0]
    assert sent["auth"] is None  # no key needed for a self-hosted endpoint
    assert sent["body"]["model"] == "jev-latest"
    assert sent["body"]["questions"]["route"]["criteria"] == {
        "route_easy": None, "route_strong": "frontier model"}
    assert "options" not in sent["body"]["questions"]["route"]
    assert out.decision == "route_strong" and out.confidence == 0.7
    assert out.raw["typesafe_confidence"] == 0.55 and out.raw["model"] == "openjev-test"
    assert out.cost_usd == 0.0  # vendor price does not apply to a self-hosted endpoint
    assert j.describe()["endpoint"] == server


def test_official_endpoint_requires_key(monkeypatch):
    monkeypatch.setenv("JEV_BACKEND", "typesafe")
    monkeypatch.delenv("JEV_ENDPOINT", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        JevJudge()
