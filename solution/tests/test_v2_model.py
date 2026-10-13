"""Adversarial provider responses; all HTTP is replaced with local fixtures."""

import json
import threading
import time
import urllib.error

import pytest

import model as model_module
from model import Budget, Client, ModelUnavailable


class Reply:
    def __init__(self, payload):
        self.body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        return self.body[:limit]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://fixture.invalid/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-secret-must-not-appear-in-logs")
    monkeypatch.setenv("ANTHROPIC_MODEL", "anthropic/claude-sonnet-4.6")
    return Client(Budget(3), time.time() + 180, threading.Event(), reserve_s=10)


def _payload(reason="stop", calls=None, content="diagnostic evidence"):
    return {
        "choices": [{"finish_reason": reason, "message": {
            "role": "assistant", "content": content, "tool_calls": calls or [],
        }}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 12, "cost": 0.031},
    }


def _call(arguments="{}", identifier="fixture-call"):
    return {"id": identifier, "type": "function", "function": {
        "name": "apply_edits", "arguments": arguments,
    }}


@pytest.mark.parametrize("arguments", ["{}", '{"edits":[{"path":"src/service.py"'])
def test_truncated_response_never_yields_executable_tool_calls(client, monkeypatch, arguments):
    payload = _payload("length", [_call(arguments)])
    monkeypatch.setattr(model_module.urllib.request, "urlopen", lambda *_args, **_kwargs: Reply(payload))
    with pytest.raises(model_module.ModelTruncated):
        client.complete([], [], max_tokens=100)
    assert client.budget.calls == 1
    assert client.budget.reserved == 0
    assert client.budget.spent == pytest.approx(0.031)


def test_content_filtered_response_cannot_supply_a_mutation(client, monkeypatch):
    monkeypatch.setattr(model_module.urllib.request, "urlopen", lambda *_args, **_kwargs: Reply(_payload("content_filter", [_call()])))
    with pytest.raises(ModelUnavailable):
        client.complete([], [])
    assert client.budget.calls == 1
    assert client.budget.reserved == 0


def test_finish_reason_is_preserved_but_not_sent_as_message_metadata(client, monkeypatch):
    requests = []

    def request(req, **_):
        requests.append(json.loads(req.data))
        return Reply(_payload("tool_calls", [_call()]))

    monkeypatch.setattr(model_module.urllib.request, "urlopen", request)
    first = client.complete([{"role": "user", "content": "inspect fixture"}], [])
    assert first["finish_reason"] == "tool_calls"
    client.complete([{"role": "user", "content": "inspect fixture"}, first,
                     {"role": "tool", "tool_call_id": "fixture-call", "content": "fixture result"}], [])
    assistant = requests[1]["messages"][1]
    assert assistant["role"] == "assistant"
    assert "finish_reason" not in assistant
    assert set(assistant) <= {"role", "content", "tool_calls", "name", "refusal"}
    assert requests[1]["model"] == "anthropic/claude-sonnet-4.6"


@pytest.mark.parametrize("payload", [
    [],
    {"choices": []},
    {"choices": [{"finish_reason": "stop", "message": "not-an-object"}]},
    _payload("tool_calls", [_call(identifier="duplicate"), _call(identifier="duplicate")]),
    _payload("tool_calls", [{"id": "invalid", "function": {"name": "read_file", "arguments": {}}}]),
    b"{malformed-provider-json",
])
def test_malformed_provider_data_fails_closed_and_releases_reservation(client, monkeypatch, payload, capsys):
    monkeypatch.setattr(model_module.urllib.request, "urlopen", lambda *_args, **_kwargs: Reply(payload))
    with pytest.raises(ModelUnavailable):
        client.complete([], [])
    assert client.budget.calls == 1
    assert client.budget.reserved == 0
    assert client.budget.spent >= 0
    assert "fixture-secret-must-not-appear-in-logs" not in capsys.readouterr().out


def test_proxy_budget_exhaustion_is_not_charged_or_retried(client, monkeypatch):
    calls = []

    def reject(req, **_):
        calls.append(req)
        raise urllib.error.HTTPError(req.full_url, 402, "budget exhausted", {}, None)

    monkeypatch.setattr(model_module.urllib.request, "urlopen", reject)
    with pytest.raises(ModelUnavailable, match="402"):
        client.complete([], [])
    assert len(calls) == 1
    assert client.budget.calls == 1
    assert client.budget.spent == 0
    assert client.budget.reserved == 0


def test_uncertain_transport_failure_keeps_conservative_charge(client, monkeypatch):
    reservations = []
    reserve = client.budget.reserve

    def remember(amount, *args, **kwargs):
        reservations.append(amount)
        return reserve(amount, *args, **kwargs)

    def fail(*_args, **_kwargs):
        raise TimeoutError("fixture timeout after possible upstream acceptance")

    monkeypatch.setattr(client.budget, "reserve", remember)
    monkeypatch.setattr(model_module.urllib.request, "urlopen", fail)
    with pytest.raises(ModelUnavailable):
        client.complete([], [])
    assert client.budget.spent == pytest.approx(reservations[0])
    assert client.budget.reserved == 0


@pytest.mark.parametrize("reason", ["cancelled", "deadline", "budget"])
def test_local_limits_prevent_any_http_request(client, monkeypatch, reason):
    if reason == "cancelled":
        client.stop.set()
    elif reason == "deadline":
        client.deadline = time.time() + 1
    else:
        client.budget.spent = client.budget.limit

    def unexpected(*_args, **_kwargs):
        pytest.fail("request must not be sent after a local stop condition")

    monkeypatch.setattr(model_module.urllib.request, "urlopen", unexpected)
    with pytest.raises(ModelUnavailable):
        client.complete([], [])
    assert client.budget.calls == 0
    assert client.budget.reserved == 0
