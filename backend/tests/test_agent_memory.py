"""Unit tests for command-bar/agent conversation memory: turns persist and
the 20-turn cap folds the oldest batch into a running summary.

Fake Mongo collection; no live Mongo/Ollama dependency.
"""
import asyncio

from services import agent_memory
from services.ai_services import AIServiceError


class FakeCollection:
    def __init__(self):
        self.docs = {}

    async def find_one(self, filt, projection=None):
        doc = self.docs.get(filt.get("username"))
        return dict(doc) if doc else None

    async def update_one(self, filt, update, upsert=False):
        self.docs[filt.get("username")] = dict(update["$set"])


class FakeDB(dict):
    def __missing__(self, key):
        self[key] = FakeCollection()
        return self[key]


class FakeMongoClient(dict):
    def __missing__(self, key):
        self[key] = FakeDB()
        return self[key]


class FakeAI:
    def __init__(self, raise_error=False):
        self.raise_error = raise_error

    async def generate_text(self, prompt, system_instruction=""):
        if self.raise_error:
            raise AIServiceError("model down")
        return "Earlier turns covered a leave-balance question and a payroll question."


def _run(coro):
    return asyncio.run(coro)


def test_turns_persist():
    mongo = FakeMongoClient()
    ai = FakeAI()
    _run(agent_memory.record_turn(mongo, ai, "alice", "employee", "user", "What is my leave balance?"))
    _run(agent_memory.record_turn(mongo, ai, "alice", "employee", "assistant", "You have 120 hours."))

    memory = _run(agent_memory.get_memory(mongo, "alice"))
    assert len(memory["turns"]) == 2
    assert memory["turns"][0]["content"] == "What is my leave balance?"
    assert memory["turns"][1]["role"] == "assistant"
    assert memory["summary"] == ""
    assert "leave balance" in agent_memory.context_block(memory)


def test_summarization_cap_folds_oldest_ten():
    mongo = FakeMongoClient()
    ai = FakeAI()
    for i in range(21):
        _run(agent_memory.record_turn(mongo, ai, "bob", "manager", "user", f"turn {i}"))

    memory = _run(agent_memory.get_memory(mongo, "bob"))
    assert len(memory["turns"]) == 11              # 21 raw turns - 10 folded away
    assert memory["turns"][0]["content"] == "turn 10"  # turns 0-9 were the ones folded
    assert memory["summary"] != ""


def test_summarization_failure_does_not_silently_drop_history():
    mongo = FakeMongoClient()
    ai = FakeAI(raise_error=True)
    for i in range(21):
        _run(agent_memory.record_turn(mongo, ai, "carol", "hrbp", "user", f"turn {i}"))

    memory = _run(agent_memory.get_memory(mongo, "carol"))
    assert len(memory["turns"]) == 21   # left over-cap rather than dropped when the model is down
    assert memory["summary"] == ""


if __name__ == "__main__":
    import sys as _sys

    tests = [
        test_turns_persist,
        test_summarization_cap_folds_oldest_ten,
        test_summarization_failure_does_not_silently_drop_history,
    ]
    passed = 0
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
        passed += 1
    print(f"{passed}/{len(tests)} passed")
    _sys.exit(0 if passed == len(tests) else 1)
