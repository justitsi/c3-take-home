"""Thread-safe, deadline-aware Sonnet client; shared reservations bound parallel spend."""
from __future__ import annotations

import json
import math
import os
import threading
import time
import urllib.error
import urllib.request

MODEL = "anthropic/claude-sonnet-4.6"


class ModelUnavailable(RuntimeError):
    pass


class Budget:
    def __init__(self, limit: float):
        self.limit = max(0.0, limit)
        self.spent = 0.0
        self.reserved = 0.0
        self.input_tokens = self.cached_tokens = self.output_tokens = self.calls = 0
        self.lock = threading.Lock()

    def reserve(self, amount: float, ceiling: float | None = None) -> None:
        with self.lock:
            limit = self.limit if ceiling is None else min(self.limit, ceiling)
            if amount > limit - self.spent - self.reserved - 0.02:
                raise ModelUnavailable("insufficient shared model budget for this request")
            self.reserved += amount

    def settle(self, reservation: float, usage: dict | None, uncertain: bool = False) -> None:
        with self.lock:
            self.reserved = max(0.0, self.reserved - reservation)
            self.calls += 1
            if uncertain:
                self.spent += reservation
                return
            usage = usage or {}
            inp = int(usage.get("prompt_tokens", 0))
            out = int(usage.get("completion_tokens", 0))
            details = usage.get("prompt_tokens_details") or {}
            cached = min(inp, int(details.get("cached_tokens", 0)))
            # Cache writes can cost 1.25x normal input; remain conservative if
            # the provider omits its actual-cost field.
            calculated = ((inp - cached) * 3.75 + cached * 0.30 + out * 15) / 1e6
            cost = usage.get("cost")
            if not isinstance(cost, (int, float)):
                cost = calculated if inp or out else reservation
            self.spent += max(0.0, float(cost))
            self.input_tokens += inp
            self.cached_tokens += cached
            self.output_tokens += out

    def summary(self) -> dict:
        with self.lock:
            return {"limit_usd": self.limit, "estimated_spend_usd": round(self.spent, 6),
                    "reserved_usd": round(self.reserved, 6), "calls": self.calls,
                    "input_tokens": self.input_tokens, "cached_tokens": self.cached_tokens,
                    "output_tokens": self.output_tokens}


class Client:
    def __init__(self, budget: Budget, deadline: float, stop: threading.Event,
                 reserve_s: float = 60):
        self.budget, self.deadline, self.stop, self.reserve_s = budget, deadline, stop, reserve_s
        self.base = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
        self.key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
        if not self.base or not self.key:
            raise ModelUnavailable("missing supplied proxy URL/token")
        if os.environ.get("ANTHROPIC_MODEL", MODEL) != MODEL:
            raise ModelUnavailable("runtime must use the permitted Sonnet model")

    def complete(self, messages: list[dict], tools: list[dict], max_tokens: int = 1800,
                 spend_cap: float | None = None, cutoff: float | None = None,
                 tool_choice: str = "auto") -> dict:
        remaining = self.deadline - time.time() - self.reserve_s
        if cutoff is not None:
            remaining = min(remaining, cutoff - time.time())
        if self.stop.is_set() or remaining <= 2:
            raise ModelUnavailable("deadline allowance reached")
        body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens,
                "temperature": 0, "tools": tools, "tool_choice": tool_choice} if tools else {
                    "model": MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
        encoded = json.dumps(body, ensure_ascii=False).encode()
        # Proxy uses approximately chars/4 and a 1.25x input reserve. chars/3
        # provides extra room for Unicode/schema estimation across requests.
        reservation = (math.ceil(len(encoded) / 3) * 3.75 + max_tokens * 15) / 1e6
        self.budget.reserve(reservation, spend_cap)
        req = urllib.request.Request(self.base + "/chat/completions", data=encoded,
                                     headers={"Authorization": "Bearer " + self.key,
                                              "Content-Type": "application/json"})
        usage = None
        charged_uncertain = True
        try:
            with urllib.request.urlopen(req, timeout=min(75, remaining)) as response:
                raw = response.read(4 * 1024 * 1024)
            result = json.loads(raw)
            usage = result.get("usage")
            message = result["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ValueError("invalid model message")
            calls = message.get("tool_calls") or []
            if not isinstance(calls, list) or len(calls) > 64:
                raise ValueError("invalid tool-call batch")
            identifiers = set()
            for call in calls:
                if not isinstance(call, dict) or not isinstance(call.get("id"), str):
                    raise ValueError("invalid tool-call identifier")
                function = call.get("function")
                if (call["id"] in identifiers or not isinstance(function, dict) or
                        not isinstance(function.get("name"), str) or
                        not isinstance(function.get("arguments"), str)):
                    raise ValueError("invalid tool-call function")
                identifiers.add(call["id"])
            if message.get("content") is not None and not isinstance(message["content"], str):
                raise ValueError("invalid assistant content")
            charged_uncertain = usage is None
            return {"role": "assistant", "content": message.get("content") or "",
                    **({"tool_calls": calls} if calls else {})}
        except urllib.error.HTTPError as error:
            # Rejected proxy requests are not charged; do not log response
            # bodies, which may contain provider identifiers or credentials.
            charged_uncertain = error.code not in (400, 401, 402, 403, 404, 429)
            if not charged_uncertain:
                usage = {"cost": 0.0}
            raise ModelUnavailable(f"proxy HTTP {error.code}") from None
        except (OSError, ValueError, KeyError, IndexError) as error:
            raise ModelUnavailable(f"model response unavailable: {type(error).__name__}") from None
        finally:
            self.budget.settle(reservation, usage, uncertain=charged_uncertain)
