import httpx
from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_todo_requires_monday_api_token(monkeypatch):
    monkeypatch.delenv("MONDAY_API_TOKEN", raising=False)
    monkeypatch.setenv("TODO_BOARD_ID", "8962223984")

    response = client.post("/todos", json={"title": "TEST - Railway"})

    assert response.status_code == 500
    assert response.json() == {
        "detail": "MONDAY_API_TOKEN environment variable is not configured."
    }


def test_create_todo_requires_board_id(monkeypatch):
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
    monkeypatch.setenv("TODO_BOARD_ID", "8962223984")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/todos", json={"title": " TEST - Railway Deploy "})

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "item_id": "12331184429",
        "title": "TEST - Railway Deploy",
    }
    assert requests == [
        {
            "url": main.MONDAY_API_URL,
            "json": {
                "query": """
    mutation CreateTodo($board_id: ID!, $item_name: String!) {
      create_item(board_id: $board_id, item_name: $item_name) {
        id
      }
    }
    """,
                "variables": {
                    "board_id": "8962223984",
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
    monkeypatch.setenv("TODO_BOARD_ID", "bad-board")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/todos", json={"title": "TEST - Railway"})

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "message": "Monday.com GraphQL mutation failed.",
            "errors": [{"message": "Board not found"}],
        }
    }
