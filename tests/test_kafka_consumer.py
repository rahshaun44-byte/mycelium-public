"""Lock in Kafka consumer commit and Athena auth behavior.

The 8abffc1 Athena /ingest lock plus enable_auto_commit=True meant a DB blip
permanently dropped pulses, and every Athena embed 401'd even when a key was set.
"""

import json
from types import SimpleNamespace

import api_node.kafka_consumer as kafka_consumer


class _FakeCursor:
    def __init__(self, fail=False):
        self.fail = fail
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if self.fail:
            raise RuntimeError("telemetry db unavailable")
        self.executed.append((sql, params))


class _FakeConn:
    def __init__(self, fail=False):
        self.fail = fail
        self.cursor_obj = _FakeCursor(fail=fail)
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        if self.fail:
            raise RuntimeError("telemetry db unavailable")
        self.committed = True


class _FakeHttpResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _sample_pulse():
    return json.dumps({
        "hostname": "qfx-yoga",
        "cpu_load_1m": 0.4,
        "ram_used_pct": 32.0,
        "timestamp": "2026-09-19T01:00:00Z",
        "status": "PULSE_OK",
        "temp_c": 41,
        "active_kem": "ML-KEM-768",
        "verdict": "ADMIT",
    })


def test_athena_headers_include_configured_key(monkeypatch):
    monkeypatch.setenv("ATHENA_API_KEY", "athena-secret")
    headers = kafka_consumer.athena_ingest_headers()
    assert headers["x-api-key"] == "athena-secret"
    assert headers["Content-Type"] == "application/json"


def test_athena_headers_fall_back_to_dashboard_key(monkeypatch):
    monkeypatch.delenv("ATHENA_API_KEY", raising=False)
    monkeypatch.setenv("DASHBOARD_API_KEY", "dash-secret")
    headers = kafka_consumer.athena_ingest_headers()
    assert headers["x-api-key"] == "dash-secret"


def test_push_to_athena_sends_api_key(monkeypatch):
    monkeypatch.setenv("ATHENA_API_KEY", "athena-secret")
    captured = {}

    def fake_urlopen(req, timeout=10):
        captured["headers"] = dict(req.header_items())
        return _FakeHttpResponse({"status": "ingested"})

    monkeypatch.setattr(kafka_consumer.urllib.request, "urlopen", fake_urlopen)
    result = kafka_consumer.push_to_athena({"text": "pulse", "source": "test"})
    assert result == {"status": "ingested"}
    header_map = {k.lower(): v for k, v in captured["headers"].items()}
    assert header_map.get("x-api-key") == "athena-secret"


def test_process_pulse_retries_when_amara_unavailable(monkeypatch):
    monkeypatch.setattr(kafka_consumer, "get_amara_connection", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    monkeypatch.setattr(kafka_consumer, "push_to_athena", lambda payload: {"status": "ingested"})
    assert kafka_consumer.process_pulse(_sample_pulse()) is False


def test_process_pulse_commits_after_amara_write_even_if_athena_fails(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setattr(kafka_consumer, "get_amara_connection", lambda: conn)
    monkeypatch.setattr(kafka_consumer, "push_to_athena", lambda payload: None)
    assert kafka_consumer.process_pulse(_sample_pulse()) is True
    assert conn.committed is True


def test_process_pulse_drops_malformed_payload_so_it_cannot_stall_the_partition():
    assert kafka_consumer.process_pulse("not-json") is True
    assert kafka_consumer.process_pulse(None) is True


def test_consume_messages_commits_only_on_success(monkeypatch):
    decisions = iter([False, True])
    commits = []

    monkeypatch.setattr(kafka_consumer, "process_pulse", lambda value: next(decisions))

    class FakeConsumer:
        def __init__(self):
            self.messages = [
                SimpleNamespace(value=_sample_pulse()),
                SimpleNamespace(value=_sample_pulse()),
            ]

        def __iter__(self):
            return iter(self.messages)

        def commit(self):
            commits.append(True)

    kafka_consumer.consume_messages(FakeConsumer())
    assert commits == [True]


def test_process_pulse_drops_optout_and_nomap_pulses(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setattr(kafka_consumer, "get_amara_connection", lambda: conn)
    athena_calls = []
    monkeypatch.setattr(kafka_consumer, "push_to_athena", lambda payload: athena_calls.append(payload))

    for tag in ["Home_optout", "Public_nomap", "Cafe_OpToUt_5G", "Work_NOMAP"]:
        pulse = json.dumps({
            "hostname": "qfx-node",
            "ssid": tag,
            "cpu_load_1m": 0.1,
            "ram_used_pct": 20.0,
            "timestamp": "2026-10-22T20:00:00Z"
        })
        # process_pulse should return True (safe to commit/drop) without touching AMARA or Athena
        assert kafka_consumer.process_pulse(pulse) is True
        assert conn.committed is False
        assert len(conn.cursor_obj.executed) == 0
        assert len(athena_calls) == 0

