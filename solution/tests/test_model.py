import json
import sys
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixer"))
from model import Budget, Client, ModelUnavailable


def test_shared_reservations_prevent_parallel_overspend():
    budget = Budget(1)
    barrier = threading.Barrier(3)
    def attempt():
        barrier.wait()
        try:
            budget.reserve(0.6)
            return True
        except ModelUnavailable:
            return False
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: attempt(), range(3)))
    assert sum(results) == 1
    assert budget.summary()["reserved_usd"] == pytest.approx(.6)


def test_cost_and_cached_usage():
    budget = Budget(3)
    budget.reserve(.2)
    budget.settle(.2, {"prompt_tokens": 10000, "completion_tokens": 1000,
                      "prompt_tokens_details": {"cached_tokens": 8000}})
    assert budget.spent == pytest.approx(.0249)
    assert budget.reserved == 0
    assert budget.cached_tokens == 8000


def test_investigation_ceiling_preserves_editor_budget():
    budget = Budget(3)
    budget.reserve(1, ceiling=1.35)
    with pytest.raises(ModelUnavailable):
        budget.reserve(.4, ceiling=1.35)
    budget.settle(1, {"cost": .8})
    budget.reserve(1.8)
    assert budget.summary()["reserved_usd"] == pytest.approx(1.8)


def test_client_deadline_does_not_issue_request(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-token")
    client = Client(Budget(3), time.time()+1, threading.Event(), reserve_s=5)
    with pytest.raises(ModelUnavailable, match="deadline"):
        client.complete([], [])
    assert client.budget.calls == 0


def test_parallel_calls_overlap_and_preserve_function_calls(monkeypatch):
    arrived = threading.Barrier(2)
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["model"] == "anthropic/claude-sonnet-4.6"
            arrived.wait(timeout=3)
            data = json.dumps({"choices": [{"message": {"content": None, "tool_calls": [
                {"id": "tool-1", "type": "function", "function": {"name": "search", "arguments": "{}"}}]}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost": .001}}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-token")
    client = Client(Budget(3), time.time()+10, threading.Event(), reserve_s=1)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda _: client.complete([], [], max_tokens=100), range(2)))
        assert all(reply["tool_calls"][0]["function"]["name"] == "search" for reply in replies)
        assert client.budget.calls == 2
        assert client.budget.spent == pytest.approx(.002)
    finally:
        server.shutdown()
        server.server_close()
