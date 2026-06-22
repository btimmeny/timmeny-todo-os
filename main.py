import os
from enum import StrEnum
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator


MONDAY_API_URL = "https://api.monday.com/v2"

app = FastAPI(title="timmeny-os", version="0.1.0")


class TodoList(StrEnum):
    TODO = "todo"
    GS = "gs"


class TodoCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    list: TodoList = TodoList.TODO

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("title must not be blank")
        return stripped_value


class TodoCreateResponse(BaseModel):
    success: bool
    item_id: str
    title: str
    list: TodoList


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/todos", response_model=TodoCreateResponse)
async def create_todo(
    payload: TodoCreateRequest,
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> TodoCreateResponse:
    verify_api_key(x_api_key=x_api_key, authorization=authorization)

    monday_token = os.getenv("MONDAY_API_TOKEN")

    if not monday_token:
        raise HTTPException(
            status_code=500,
            detail="MONDAY_API_TOKEN environment variable is not configured.",
        )

    target = get_todo_target(payload.list)

    item_id = await create_monday_item(
        token=monday_token,
        board_id=target["board_id"],
        group_id=target["group_id"],
        title=payload.title,
    )

    return TodoCreateResponse(
        success=True,
        item_id=item_id,
        title=payload.title,
        list=payload.list,
    )


def verify_api_key(
    x_api_key: str | None,
    authorization: str | None,
) -> None:
    expected_api_key = os.getenv("TIMMENY_OS_API_KEY")
    if not expected_api_key:
        return

    provided_api_key = x_api_key or extract_bearer_token(authorization)

    if provided_api_key != expected_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key.",
        )


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    return token


def get_todo_target(todo_list: TodoList) -> dict[str, str | None]:
    env_prefix = "TODO" if todo_list == TodoList.TODO else "GS_TODO"
    board_id_variable = f"{env_prefix}_BOARD_ID"
    group_id_variable = f"{env_prefix}_GROUP_ID"

    board_id = os.getenv(board_id_variable)
    if not board_id:
        raise HTTPException(
            status_code=500,
            detail=f"{board_id_variable} environment variable is not configured.",
        )

    return {
        "board_id": board_id,
        "group_id": os.getenv(group_id_variable) or None,
    }


async def create_monday_item(
    token: str,
    board_id: str,
    group_id: str | None,
    title: str,
) -> str:
    query = """
    mutation CreateTodo($board_id: ID!, $group_id: String, $item_name: String!) {
      create_item(board_id: $board_id, group_id: $group_id, item_name: $item_name) {
        id
      }
    }
    """

    body = {
        "query": query,
        "variables": {
            "board_id": board_id,
            "group_id": group_id,
            "item_name": title,
        },
    }

    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(MONDAY_API_URL, json=body, headers=headers)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Timed out while contacting Monday.com.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Monday.com returned HTTP {exc.response.status_code}.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not contact Monday.com.",
        ) from exc

    try:
        response_body: dict[str, Any] = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Monday.com returned an invalid JSON response.",
        ) from exc

    monday_errors = response_body.get("errors")
    if monday_errors:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Monday.com GraphQL mutation failed.",
                "errors": monday_errors,
            },
        )

    item_id = (
        response_body.get("data", {})
        .get("create_item", {})
        .get("id")
    )

    if not item_id:
        raise HTTPException(
            status_code=502,
            detail="Monday.com response did not include a created item id.",
        )

    return str(item_id)
