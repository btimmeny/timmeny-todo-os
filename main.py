import json
import os
from datetime import date
from enum import StrEnum
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator


MONDAY_API_URL = "https://api.monday.com/v2"
ACTION_GROUP_COLUMN_TITLE = "Action Group"
ACTION_DATE_COLUMN_TITLE = "Action Date"
ACTION_COLUMN_TITLE = "Action"

app = FastAPI(title="Timmeny-ToDo-OS", version="0.1.0")


class TodoList(StrEnum):
    TODO = "todo"
    GS = "gs"


class TodoListFilter(StrEnum):
    ALL = "all"
    TODO = "todo"
    GS = "gs"


class TodoActionMetadata(BaseModel):
    action_group: str | None = Field(default=None, max_length=255)
    action_date: date | None = None
    action: str | None = Field(default=None, max_length=255)

    @field_validator("action_group", "action")
    @classmethod
    def optional_strings_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped_value = value.strip()
        return stripped_value or None


class TodoCreateRequest(TodoActionMetadata):
    title: str = Field(..., min_length=1, max_length=255)
    list: TodoList = TodoList.TODO

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("title must not be blank")
        return stripped_value


class TodoCreateResponse(TodoActionMetadata):
    success: bool
    item_id: str
    title: str
    list: TodoList


class TodoUpdateActionMetadataRequest(TodoActionMetadata):
    list: TodoList


class TodoUpdateActionMetadataResponse(TodoActionMetadata):
    success: bool
    item_id: str
    list: TodoList


class TodoItem(TodoActionMetadata):
    item_id: str
    title: str
    list: TodoList
    group_id: str | None = None
    group_title: str | None = None


class TodoListResponse(BaseModel):
    success: bool
    count: int
    items: list[TodoItem]


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/todos", response_model=TodoListResponse)
async def list_todos(
    list_filter: TodoListFilter = Query(default=TodoListFilter.ALL, alias="list"),
    limit: int = Query(default=25, ge=1, le=100),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> TodoListResponse:
    verify_api_key(x_api_key=x_api_key, authorization=authorization)

    monday_token = get_monday_token()
    todo_lists = get_todo_lists_for_filter(list_filter)
    items: list[TodoItem] = []

    for todo_list in todo_lists:
        target = get_todo_target(todo_list)
        monday_items = await get_monday_items(
            token=monday_token,
            board_id=target["board_id"],
            limit=limit,
        )
        items.extend(
            TodoItem(
                item_id=item["id"],
                title=item["name"],
                list=todo_list,
                group_id=get_monday_item_group(item).get("id"),
                group_title=get_monday_item_group(item).get("title"),
                **get_monday_action_metadata(item),
            )
            for item in monday_items
        )

    return TodoListResponse(success=True, count=len(items), items=items)


@app.post("/todos", response_model=TodoCreateResponse)
async def create_todo(
    payload: TodoCreateRequest,
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> TodoCreateResponse:
    verify_api_key(x_api_key=x_api_key, authorization=authorization)

    monday_token = get_monday_token()
    target = get_todo_target(payload.list)
    column_values = await build_action_column_values(
        token=monday_token,
        board_id=target["board_id"],
        action_group=payload.action_group,
        action_date=payload.action_date,
        action=payload.action,
    )

    item_id = await create_monday_item(
        token=monday_token,
        board_id=target["board_id"],
        group_id=target["group_id"],
        title=payload.title,
        column_values=column_values,
    )

    return TodoCreateResponse(
        success=True,
        item_id=item_id,
        title=payload.title,
        list=payload.list,
        action_group=payload.action_group,
        action_date=payload.action_date,
        action=payload.action,
    )


@app.patch("/todos/{item_id}/action-metadata", response_model=TodoUpdateActionMetadataResponse)
async def update_todo_action_metadata(
    item_id: str,
    payload: TodoUpdateActionMetadataRequest,
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> TodoUpdateActionMetadataResponse:
    verify_api_key(x_api_key=x_api_key, authorization=authorization)

    monday_token = get_monday_token()
    target = get_todo_target(payload.list)
    column_values = await build_action_column_values(
        token=monday_token,
        board_id=target["board_id"],
        action_group=payload.action_group,
        action_date=payload.action_date,
        action=payload.action,
    )

    if not column_values:
        raise HTTPException(
            status_code=422,
            detail="At least one action metadata field is required.",
        )

    updated_item_id = await update_monday_item_columns(
        token=monday_token,
        board_id=target["board_id"],
        item_id=item_id,
        column_values=column_values,
    )

    return TodoUpdateActionMetadataResponse(
        success=True,
        item_id=updated_item_id,
        list=payload.list,
        action_group=payload.action_group,
        action_date=payload.action_date,
        action=payload.action,
    )


def get_monday_token() -> str:
    monday_token = os.getenv("MONDAY_API_TOKEN")
    if not monday_token:
        raise HTTPException(
            status_code=500,
            detail="MONDAY_API_TOKEN environment variable is not configured.",
        )
    return monday_token


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


def get_todo_lists_for_filter(list_filter: TodoListFilter) -> list[TodoList]:
    if list_filter == TodoListFilter.TODO:
        return [TodoList.TODO]
    if list_filter == TodoListFilter.GS:
        return [TodoList.GS]
    return [TodoList.TODO, TodoList.GS]


def get_monday_item_group(item: dict[str, Any]) -> dict[str, Any]:
    group = item.get("group")
    if not isinstance(group, dict):
        return {}
    return group


def get_monday_action_metadata(item: dict[str, Any]) -> dict[str, str | None]:
    metadata = {
        "action_group": None,
        "action_date": None,
        "action": None,
    }
    column_values = item.get("column_values")
    if not isinstance(column_values, list):
        return metadata

    for column_value in column_values:
        if not isinstance(column_value, dict):
            continue
        column = column_value.get("column")
        if not isinstance(column, dict):
            continue

        title = column.get("title")
        text = column_value.get("text")
        if not text:
            continue

        if title == ACTION_GROUP_COLUMN_TITLE:
            metadata["action_group"] = text
        elif title == ACTION_DATE_COLUMN_TITLE:
            metadata["action_date"] = text
        elif title == ACTION_COLUMN_TITLE:
            metadata["action"] = text

    return metadata


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


async def get_monday_items(token: str, board_id: str, limit: int) -> list[dict[str, Any]]:
    query = """
    query GetTodoItems($board_id: ID!, $limit: Int!) {
      boards(ids: [$board_id]) {
        columns {
          id
          title
        }
        items_page(limit: $limit) {
          items {
            id
            name
            group {
              id
              title
            }
            column_values {
              id
              text
              value
            }
          }
        }
      }
    }
    """

    response_body = await execute_monday_graphql(
        token=token,
        body={
            "query": query,
            "variables": {
                "board_id": board_id,
                "limit": limit,
            },
        },
    )

    boards = response_body.get("data", {}).get("boards", [])
    if not boards:
        raise HTTPException(
            status_code=502,
            detail="Monday.com response did not include board data.",
        )

    board = boards[0]
    columns_by_id = {
        column["id"]: column
        for column in board.get("columns", [])
        if isinstance(column, dict) and column.get("id")
    }
    items = board.get("items_page", {}).get("items", [])
    for item in items:
        if not isinstance(item, dict):
            continue
        column_values = item.get("column_values")
        if not isinstance(column_values, list):
            continue
        for column_value in column_values:
            if not isinstance(column_value, dict) or column_value.get("column"):
                continue
            column = columns_by_id.get(column_value.get("id"))
            if column:
                column_value["column"] = column
    return items


async def create_monday_item(
    token: str,
    board_id: str,
    group_id: str | None,
    title: str,
    column_values: dict[str, Any] | None = None,
) -> str:
    query = """
    mutation CreateTodo($board_id: ID!, $group_id: String, $item_name: String!, $column_values: JSON) {
      create_item(board_id: $board_id, group_id: $group_id, item_name: $item_name, column_values: $column_values) {
        id
      }
    }
    """

    response_body = await execute_monday_graphql(
        token=token,
        body={
            "query": query,
            "variables": {
                "board_id": board_id,
                "group_id": group_id,
                "item_name": title,
                "column_values": serialize_column_values(column_values),
            },
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


async def update_monday_item_columns(
    token: str,
    board_id: str,
    item_id: str,
    column_values: dict[str, Any],
) -> str:
    query = """
    mutation UpdateTodoColumns($board_id: ID!, $item_id: ID!, $column_values: JSON!) {
      change_multiple_column_values(board_id: $board_id, item_id: $item_id, column_values: $column_values) {
        id
      }
    }
    """

    response_body = await execute_monday_graphql(
        token=token,
        body={
            "query": query,
            "variables": {
                "board_id": board_id,
                "item_id": item_id,
                "column_values": serialize_column_values(column_values),
            },
        },
    )

    updated_item_id = (
        response_body.get("data", {})
        .get("change_multiple_column_values", {})
        .get("id")
    )

    if not updated_item_id:
        raise HTTPException(
            status_code=502,
            detail="Monday.com response did not include an updated item id.",
        )

    return str(updated_item_id)


async def build_action_column_values(
    token: str,
    board_id: str,
    action_group: str | None,
    action_date: date | None,
    action: str | None,
) -> dict[str, Any]:
    requested_columns = {
        ACTION_GROUP_COLUMN_TITLE: action_group,
        ACTION_DATE_COLUMN_TITLE: action_date,
        ACTION_COLUMN_TITLE: action,
    }
    if all(value is None for value in requested_columns.values()):
        return {}

    columns_by_title = await get_board_columns_by_title(token=token, board_id=board_id)
    column_values: dict[str, Any] = {}

    if action_group is not None:
        column = require_board_column(columns_by_title, ACTION_GROUP_COLUMN_TITLE)
        column_values[column["id"]] = action_group

    if action_date is not None:
        column = require_board_column(columns_by_title, ACTION_DATE_COLUMN_TITLE)
        column_values[column["id"]] = {"date": action_date.isoformat()}

    if action is not None:
        column = require_board_column(columns_by_title, ACTION_COLUMN_TITLE)
        column_values[column["id"]] = build_action_column_value(column, action)

    return column_values


def build_action_column_value(column: dict[str, Any], action: str) -> dict[str, Any]:
    if column.get("type") == "status":
        return {"label": action}
    return {"labels": [action]}


async def get_board_columns_by_title(
    token: str,
    board_id: str,
) -> dict[str, dict[str, Any]]:
    query = """
    query GetBoardColumns($board_id: ID!) {
      boards(ids: [$board_id]) {
        columns {
          id
          title
          type
        }
      }
    }
    """

    response_body = await execute_monday_graphql(
        token=token,
        body={
            "query": query,
            "variables": {
                "board_id": board_id,
            },
        },
    )

    boards = response_body.get("data", {}).get("boards", [])
    if not boards:
        raise HTTPException(
            status_code=502,
            detail="Monday.com response did not include board column data.",
        )

    columns = boards[0].get("columns", [])
    return {
        column["title"]: column
        for column in columns
        if isinstance(column, dict) and column.get("title") and column.get("id")
    }


def require_board_column(
    columns_by_title: dict[str, dict[str, Any]],
    title: str,
) -> dict[str, Any]:
    column = columns_by_title.get(title)
    if not column:
        raise HTTPException(
            status_code=502,
            detail=f'Monday.com board is missing the "{title}" column.',
        )
    return column


def serialize_column_values(column_values: dict[str, Any] | None) -> str | None:
    if not column_values:
        return None
    return json.dumps(column_values)


async def execute_monday_graphql(token: str, body: dict[str, Any]) -> dict[str, Any]:
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
                "message": "Monday.com GraphQL request failed.",
                "errors": monday_errors,
            },
        )

    return response_body
