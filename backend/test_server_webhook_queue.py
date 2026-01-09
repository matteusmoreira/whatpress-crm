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

    def or_(self, expr):
        self._ops.append(("or_", expr))
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


def test_agent_cannot_access_admin_assigned_conversation(monkeypatch):
    import backend.server as server
    from fastapi.testclient import TestClient

    def table_handler(name, ops):
        if name == "conversations":
            conversation_id = None
            for op in ops:
                if op[0] == "eq" and op[1] == "id":
                    conversation_id = op[2]
                    break
            if conversation_id == "conv_admin":
                return _Result(
                    data=[
                        {
                            "id": "conv_admin",
                            "tenant_id": "tenant1",
                            "assigned_to": "admin1",
                        }
                    ]
                )
            if conversation_id == "conv_unassigned":
                return _Result(
                    data=[
                        {
                            "id": "conv_unassigned",
                            "tenant_id": "tenant1",
                            "assigned_to": None,
                        }
                    ]
                )
            return _Result(data=[])

        if name == "messages":
            return _Result(data=[])

        return _Result(data=[])

    monkeypatch.setattr(server, "supabase", _SupabaseStub(table_handler))
    server.app.dependency_overrides[server.verify_token] = lambda: {
        "user_id": "agent1",
        "role": "agent",
        "tenant_id": "tenant1",
    }

    client = TestClient(server.app)

    denied = client.get("/api/messages", params={"conversation_id": "conv_admin"})
    assert denied.status_code == 403

    allowed = client.get("/api/messages", params={"conversation_id": "conv_unassigned"})
    assert allowed.status_code == 200


def test_agent_cannot_send_media_message_to_admin_assigned_conversation(monkeypatch):
    import backend.server as server
    from fastapi.testclient import TestClient

    def table_handler(name, ops):
        if name == "conversations":
            conversation_id = None
            for op in ops:
                if op[0] == "eq" and op[1] == "id":
                    conversation_id = op[2]
                    break
            if conversation_id == "conv_admin":
                return _Result(
                    data=[
                        {
                            "id": "conv_admin",
                            "tenant_id": "tenant1",
                            "assigned_to": "admin1",
                        }
                    ]
                )
            return _Result(data=[])

        return _Result(data=[])

    monkeypatch.setattr(server, "supabase", _SupabaseStub(table_handler))
    server.app.dependency_overrides[server.verify_token] = lambda: {
        "user_id": "agent1",
        "role": "agent",
        "tenant_id": "tenant1",
    }

    client = TestClient(server.app)
    resp = client.post(
        "/api/messages/media",
        data={
            "conversation_id": "conv_admin",
            "media_type": "image",
            "media_url": "https://example.com/x.jpg",
            "media_name": "x.jpg",
            "content": "teste",
        },
    )
    assert resp.status_code == 403


def test_agent_conversations_list_uses_assignment_filter(monkeypatch):
    import backend.server as server
    from fastapi.testclient import TestClient

    saw_assignment_or = {"value": False}

    def table_handler(name, ops):
        if name == "conversations":
            for op in ops:
                if op[0] == "or_" and isinstance(op[1], str):
                    if "assigned_to.is.null" in op[1] and "assigned_to.eq.agent1" in op[1]:
                        saw_assignment_or["value"] = True
            return _Result(
                data=[
                    {
                        "id": "conv_unassigned",
                        "tenant_id": "tenant1",
                        "connection_id": "conn1",
                        "contact_phone": "5511999999999",
                        "contact_name": "Contato",
                        "contact_avatar": None,
                        "status": "open",
                        "assigned_to": None,
                        "last_message_at": None,
                        "unread_count": 0,
                        "last_message_preview": "",
                        "created_at": None,
                    }
                ]
            )

        if name == "connections":
            return _Result(data=[])

        return _Result(data=[])

    monkeypatch.setattr(server, "supabase", _SupabaseStub(table_handler))
    server.app.dependency_overrides[server.verify_token] = lambda: {
        "user_id": "agent1",
        "role": "agent",
        "tenant_id": "tenant1",
    }

    client = TestClient(server.app)
    resp = client.get("/api/conversations", params={"tenant_id": "tenant1"})
    assert resp.status_code == 200
    assert saw_assignment_or["value"] is True


def test_agent_cannot_create_connection(monkeypatch):
    import backend.server as server
    from fastapi.testclient import TestClient

    def table_handler(_name, _ops):
        return _Result(data=[])

    monkeypatch.setattr(server, "supabase", _SupabaseStub(table_handler))
    server.app.dependency_overrides[server.verify_token] = lambda: {
        "user_id": "agent1",
        "role": "agent",
        "tenant_id": "tenant1",
    }

    client = TestClient(server.app)
    resp = client.post(
        "/api/connections",
        json={
            "tenant_id": "tenant1",
            "provider": "evolution",
            "instance_name": "inst",
            "phone_number": "",
        },
    )
    assert resp.status_code == 403


def test_agent_cannot_list_connections_from_other_tenant(monkeypatch):
    import backend.server as server
    from fastapi.testclient import TestClient

    def table_handler(_name, _ops):
        return _Result(data=[])

    monkeypatch.setattr(server, "supabase", _SupabaseStub(table_handler))
    server.app.dependency_overrides[server.verify_token] = lambda: {
        "user_id": "agent1",
        "role": "agent",
        "tenant_id": "tenant1",
    }

    client = TestClient(server.app)
    resp = client.get("/api/connections", params={"tenant_id": "tenant2"})
    assert resp.status_code == 403
