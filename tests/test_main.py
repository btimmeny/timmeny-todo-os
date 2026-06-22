import httpx
from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_todo_requires_monday_api_token(monkeypatch):
    monkeypatch.delenv("TIMMENY_OS_API_KEY", raising=False)
    monkeypatch.delenv("MONDAY_API_TOKEN", raising=False)
    monkeypatch.setenv("TODO_BOARD_ID", "8962223984")

    response = client.post("/todos", json={"title": "TEST - Railway"})

    assert response.status_code == 500
    assert response.json() == {
        "detail": "MONDAY_API_TOKEN environment variable is not configured."
    }


def test_create_todo_requires_board_id(monkeypatch):
    monkeypatch.delenv("TIMMENY_OS_API_KEY", raising=False)
    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.delenv("TODO_BOARD_ID", raising=False)

    response = client.post("/todos", json={"title": "TEST - Railway"})

    assert response.status_code == 500
    assert response.json() == {
        "detail": "TODO_BOARD_ID environment variable is not configured."
    }


def test_create_todo_creates_monday_item(monkeypatch):
    requests = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, json, headers):
            requests.append({"url": url, "json": json, "headers": headers})
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={"data": {"create_item": {"id": "12331184429"}}},
                request=request,
            )

    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.delenv("TIMMENY_OS_API_KEY", raising=False)
    monkeypatch.setenv("TODO_BOARD_ID", "8962223984")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/todos", json={"title": " TEST - Railway Deploy "})

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "item_id": "12331184429",
        "title": "TEST - Railway Deploy",
        "list": "todo",
    }
    assert requests == [
        {
            "url": main.MONDAY_API_URL,
            "json": {
                "query": """
    mutation CreateTodo($board_id: ID!, $group_id: String, $item_name: String!) {
      create_item(board_id: $board_id, group_id: $group_id, item_name: $item_name) {
        id
      }
    }
    """,
                "variables": {
                    "board_id": "8962223984",
                    "group_id": None,
                    "item_name": "TEST - Railway Deploy",
                },
            },
            "headers": {
                "Authorization": "test-token",
                "Content-Type": "application/json",
            },
        }
    ]


def test_create_todo_handles_monday_graphql_errors(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, json, headers):
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={"errors": [{"message": "Board not found"}]},
                request=request,
            )

    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.delenv("TIMMENY_OS_API_KEY", raising=False)
    monkeypatch.setenv("TODO_BOARD_ID", "bad-board")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/todos", json={"title": "TEST - Railway"})

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "message": "Monday.com GraphQL request failed.",
            "errors": [{"message": "Board not found"}],
        }
    }


def test_create_todo_can_target_gs_list(monkeypatch):
    requests = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, json, headers):
            requests.append(json)
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={"data": {"create_item": {"id": "12331184430"}}},
                request=request,
            )

    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.delenv("TIMMENY_OS_API_KEY", raising=False)
    monkeypatch.setenv("GS_TODO_BOARD_ID", "111222333")
    monkeypatch.setenv("GS_TODO_GROUP_ID", "topics")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        "/todos",
        json={"title": "GS follow-up", "list": "gs"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "item_id": "12331184430",
        "title": "GS follow-up",
        "list": "gs",
    }
    assert requests[0]["variables"] == {
        "board_id": "111222333",
        "group_id": "topics",
        "item_name": "GS follow-up",
    }


def test_create_todo_requires_gs_board_id(monkeypatch):
    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.delenv("TIMMENY_OS_API_KEY", raising=False)
    monkeypatch.delenv("GS_TODO_BOARD_ID", raising=False)

    response = client.post(
        "/todos",
        json={"title": "GS follow-up", "list": "gs"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "GS_TODO_BOARD_ID environment variable is not configured."
    }


def test_create_todo_accepts_configured_api_key(monkeypatch):
    requests = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, json, headers):
            requests.append(json)
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={"data": {"create_item": {"id": "12331184432"}}},
                request=request,
            )

    monkeypatch.setenv("TIMMENY_OS_API_KEY", "app-key")
    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.setenv("TODO_BOARD_ID", "8962223984")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        "/todos",
        json={"title": "Protected todo"},
        headers={"X-API-Key": "app-key"},
    )

    assert response.status_code == 200
    assert requests[0]["variables"]["item_name"] == "Protected todo"


def test_create_todo_accepts_bearer_api_key(monkeypatch):
    requests = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, json, headers):
            requests.append(json)
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={"data": {"create_item": {"id": "12331184433"}}},
                request=request,
            )

    monkeypatch.setenv("TIMMENY_OS_API_KEY", "app-key")
    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.setenv("TODO_BOARD_ID", "8962223984")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        "/todos",
        json={"title": "Bearer protected todo"},
        headers={"Authorization": "Bearer app-key"},
    )

    assert response.status_code == 200
    assert requests[0]["variables"]["item_name"] == "Bearer protected todo"


def test_create_todo_rejects_missing_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("TIMMENY_OS_API_KEY", "app-key")
    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.setenv("TODO_BOARD_ID", "8962223984")

    response = client.post("/todos", json={"title": "Protected todo"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_list_todos_returns_items_from_both_boards(monkeypatch):
    requests = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, json, headers):
            requests.append(json)
            board_id = json["variables"]["board_id"]
            request = httpx.Request("POST", url)
            items_by_board = {
                "todo-board": [
                    {
                        "id": "1",
                        "name": "regular item",
                        "group": {"id": "todo-group", "title": "To Do"},
                    }
                ],
                "gs-board": [
                    {
                        "id": "2",
                        "name": "gs item",
                        "group": {"id": "gs-group", "title": "Action Items"},
                    }
                ],
            }
            return httpx.Response(
                200,
                json={
                    "data": {
                        "boards": [
                            {
                                "items_page": {
                                    "items": items_by_board[board_id],
                                }
                            }
                        ]
                    }
                },
                request=request,
            )

    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.delenv("TIMMENY_OS_API_KEY", raising=False)
    monkeypatch.setenv("TODO_BOARD_ID", "todo-board")
    monkeypatch.setenv("GS_TODO_BOARD_ID", "gs-board")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/todos")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "count": 2,
        "items": [
            {
                "item_id": "1",
                "title": "regular item",
                "list": "todo",
                "group_id": "todo-group",
                "group_title": "To Do",
            },
            {
                "item_id": "2",
                "title": "gs item",
                "list": "gs",
                "group_id": "gs-group",
                "group_title": "Action Items",
            },
        ],
    }
    assert [request["variables"]["board_id"] for request in requests] == [
        "todo-board",
        "gs-board",
    ]
    assert [request["variables"]["limit"] for request in requests] == [25, 25]


def test_list_todos_can_filter_to_gs(monkeypatch):
    requests = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, json, headers):
            requests.append(json)
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={
                    "data": {
                        "boards": [
                            {
                                "items_page": {
                                    "items": [
                                        {
                                            "id": "2",
                                            "name": "gs item",
                                            "group": None,
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                },
                request=request,
            )

    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.delenv("TIMMENY_OS_API_KEY", raising=False)
    monkeypatch.setenv("GS_TODO_BOARD_ID", "gs-board")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/todos?list=gs&limit=10")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "count": 1,
        "items": [
            {
                "item_id": "2",
                "title": "gs item",
                "list": "gs",
                "group_id": None,
                "group_title": None,
            }
        ],
    }
    assert len(requests) == 1
    assert requests[0]["variables"] == {
        "board_id": "gs-board",
        "limit": 10,
    }


def test_list_todos_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("TIMMENY_OS_API_KEY", "app-key")
    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token")
    monkeypatch.setenv("TODO_BOARD_ID", "todo-board")

    response = client.get("/todos")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}
