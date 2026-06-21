import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator


MONDAY_API_URL = "https://api.monday.com/v2"

app = FastAPI(title="timmeny-os", version="0.1.0")


class TodoCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)

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


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/todos", response_model=TodoCreateResponse)
async def create_todo(payload: TodoCreateRequest) -> TodoCreateResponse:
    monday_token = os.getenv("MONDAY_API_TOKEN")
    todo_board_id = os.getenv("TODO_BOARD_ID")

    if not monday_token:
        raise HTTPException(
            status_code=500,
            detail="MONDAY_API_TOKEN environment variable is not configured.",
        )

    if not todo_board_id:
        raise HTTPException(
            status_code=500,
            detail="TODO_BOARD_ID environment variable is not configured.",
        )

    item_id = await create_monday_item(
        token=monday_token,
        board_id=todo_board_id,
        title=payload.title,
    )

    return TodoCreateResponse(success=True, item_id=item_id, title=payload.title)


async def create_monday_item(token: str, board_id: str, title: str) -> str:
    query = """
    mutation CreateTodo($board_id: ID!, $item_name: String!) {
      create_item(board_id: $board_id, item_name: $item_name) {
        id
      }
    }
    """

    body = {
        "query": query,
        "variables": {
            "board_id": board_id,
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
