import pytest


class _Result:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


class _Query:
    def __init__(self, handler):
        self._handler = handler
        self._ops = []

    def select(self, *args, **kwargs):
        self._ops.append(("select", args, kwargs))
        return self

    def eq(self, field, value):
        self._ops.append(("eq", field, value))
        return self

    def limit(self, n):
        self._ops.append(("limit", n))
        return self

    def order(self, *args, **kwargs):
        self._ops.append(("order", args, kwargs))
        return self

    def range(self, start, end):
        self._ops.append(("range", start, end))
        return self

    def insert(self, data):
        self._ops.append(("insert", data))
        return self

    def update(self, data):
        self._ops.append(("update", data))
        return self

    def execute(self):
        return self._handler(self._ops)


class _SupabaseStub:
    def __init__(self, table_handler):
        self._table_handler = table_handler

    def table(self, name):
        return _Query(lambda ops: self._table_handler(name, ops))


@pytest.mark.anyio
async def test_webhook_transient_connection_error_queues_event(monkeypatch):
    import backend.server as server

    server._DB_WRITE_QUEUE.clear()

    def parse_stub(_payload):
        return {
            "event": "message",
            "from_me": False,
            "remote_jid": "5521999998888",
            "remote_jid_raw": "5521999998888@s.whatsapp.net",
            "content": "oi",
            "timestamp": "1700000000",
            "message_id": "MSG1",
            "type": "text",
        }

    monkeypatch.setattr(
        server.evolution_api,
        "parse_webhook_message",
        parse_stub,
    )

    def table_handler(_name, _ops):
        raise Exception("503 service unavailable")

    monkeypatch.setattr(server, "supabase", _SupabaseStub(table_handler))

    resp = await server._process_evolution_webhook(
        "inst1",
        {"event": "MESSAGES_UPSERT"},
        from_queue=False,
    )

    assert resp.get("queued") is True
    assert len(server._DB_WRITE_QUEUE) == 1
    assert server._DB_WRITE_QUEUE[0].get("kind") == "webhook_event"


def test_normalize_phone_number_variants():
    import backend.server as server

    assert (
        server.normalize_phone_number("+55 (21) 99999-8888")
        == "5521999998888"
    )
    assert server.normalize_phone_number("21 99999-8888") == "5521999998888"


def test_transient_db_error_detection():
    import backend.server as server

    assert server._is_transient_db_error(Exception("502 Bad Gateway")) is True
    assert server._is_transient_db_error(Exception("PGRST205")) is False
