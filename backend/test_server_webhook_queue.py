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


@pytest.mark.anyio
async def test_webhook_creates_contact_when_from_me_true(monkeypatch):
    import backend.server as server

    inserted_contacts = []

    def parse_stub(_payload):
        return {
            "event": "message",
            "from_me": True,
            "remote_jid": "5521999998888",
            "remote_jid_raw": "5521999998888@s.whatsapp.net",
            "content": "oi",
            "timestamp": "1700000000",
            "message_id": "MSG1",
            "type": "text",
        }

    async def get_profile_picture_stub(_instance_name, _phone):
        return {}

    monkeypatch.setattr(
        server.evolution_api,
        "parse_webhook_message",
        parse_stub,
    )
    monkeypatch.setattr(
        server.evolution_api,
        "get_profile_picture",
        get_profile_picture_stub,
    )

    def table_handler(name, ops):
        if name == "connections":
            return _Result(
                data=[
                    {
                        "id": "conn1",
                        "tenant_id": "tenant1",
                        "tenants": {},
                    }
                ]
            )

        if name == "conversations":
            for op in ops:
                if op[0] == "select":
                    return _Result(data=[])
                if op[0] == "insert":
                    conv = dict(op[1])
                    return _Result(
                        data=[
                            {
                                "id": "conv1",
                                "unread_count": 0,
                                **conv,
                            }
                        ]
                    )
                if op[0] == "update":
                    return _Result(data=[{}])
            return _Result(data=[])

        if name == "contacts":
            for op in ops:
                if op[0] == "select":
                    return _Result(data=[])
                if op[0] == "insert":
                    payload = dict(op[1])
                    inserted_contacts.append(payload)
                    return _Result(data=[{"id": "contact1", **payload}])
                if op[0] == "update":
                    return _Result(data=[{}])
            return _Result(data=[])

        if name == "messages":
            for op in ops:
                if op[0] == "insert":
                    return _Result(data=[{"id": "msg1", **dict(op[1])}])
                if op[0] == "update":
                    return _Result(data=[{}])
            return _Result(data=[])

        if name == "tenants":
            for op in ops:
                if op[0] == "select":
                    return _Result(data=[{"messages_this_month": 0}])
                if op[0] == "update":
                    return _Result(data=[{}])
            return _Result(data=[])

        if name in {"auto_messages", "audit_logs"}:
            return _Result(data=[])

        return _Result(data=[])

    monkeypatch.setattr(server, "supabase", _SupabaseStub(table_handler))

    resp = await server._process_evolution_webhook(
        "inst1",
        {"event": "MESSAGES_UPSERT"},
        from_queue=False,
    )

    assert resp.get("success") is True
    assert len(inserted_contacts) == 1
    assert inserted_contacts[0].get("phone") == "5521999998888"
    assert inserted_contacts[0].get("source") == "whatsapp"


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


def test_login_db_error_returns_cors_headers(monkeypatch):
    import backend.server as server
    from fastapi.testclient import TestClient

    class _ExplodingQuery:
        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            raise Exception("db down")

    class _SupabaseExploding:
        def table(self, _name):
            return _ExplodingQuery()

    monkeypatch.setattr(server, "supabase", _SupabaseExploding())

    client = TestClient(server.app)
    origin = "https://whatpress-crm.vercel.app"

    resp = client.post(
        "/api/auth/login",
        headers={"Origin": origin},
        json={"email": "x@y.com", "password": "bad"},
    )
    assert resp.status_code == 503
    assert resp.headers.get("access-control-allow-origin") == origin

    preflight = client.options(
        "/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") == origin
