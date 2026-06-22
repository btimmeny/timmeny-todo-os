# Timmeny-ToDo-OS

A personal todo operating system for capturing tasks and action items into the right Monday.com boards.

This repository starts as a lightweight FastAPI service for the Timmeny-ToDo-OS workflow, plus a place to define the principles, interfaces, and routines that make the system useful before hardening more todo workflows.

## API

### `GET /health`

Returns service health.

```json
{
  "status": "ok"
}
```

### `POST /todos`

Creates a todo item on a Monday.com board.

Request:

```json
{
  "title": "TEST - Railway",
  "list": "todo",
  "action_group": "Launch",
  "action_date": "2026-06-21",
  "action": "Decision"
}
```

`list` is optional and defaults to `todo`. Use `gs` to create the item in the GS todo target.
`action_group`, `action_date`, and `action` are optional Monday.com column values.

Response:

```json
{
  "success": true,
  "item_id": "...",
  "title": "TEST - Railway",
  "list": "todo",
  "action_group": "Launch",
  "action_date": "2026-06-21",
  "action": "Decision"
}
```

### `GET /todos`

Reads todo items from Monday.com.

Query parameters:

- `list`: `all`, `todo`, or `gs`. Defaults to `all`.
- `limit`: maximum items to read from each selected board. Defaults to `25`, max `100`.

Example:

```bash
curl https://timmeny-os-production.up.railway.app/todos?list=all \
  -H "Authorization: Bearer $TIMMENY_OS_API_KEY"
```

Response:

```json
{
  "success": true,
  "count": 2,
  "items": [
    {
      "item_id": "...",
      "title": "follow up",
      "list": "todo",
      "group_id": "...",
      "group_title": "To Do",
      "action_group": "Launch",
      "action_date": "2026-06-21",
      "action": "Decision"
    }
  ]
}
```

### `PATCH /todos/{item_id}/action-metadata`

Updates the Monday.com action metadata columns for an existing todo item.

Request:

```json
{
  "list": "gs",
  "action_group": "Partnerships",
  "action_date": "2026-06-21",
  "action": "Decision"
}
```

At least one of `action_group`, `action_date`, or `action` is required. The board must have columns named exactly `Action Group`, `Action Date`, and `Action` when those values are used.

## Configuration

Set these environment variables:

- `MONDAY_API_TOKEN`: Monday.com API token.
- `TIMMENY_OS_API_KEY`: optional shared API key for protected clients such as a GPT Action.
- `TODO_BOARD_ID`: Monday.com board id for `To Do List`.
- `TODO_GROUP_ID`: optional Monday.com group id for regular todos.
- `GS_TODO_BOARD_ID`: Monday.com board id for `GS | Initiatives & Action Items`.
- `GS_TODO_GROUP_ID`: optional Monday.com group id for GS todos.

The organize workflow also expects these Monday.com columns on each board:

- `Action Group`: text column for GPT-selected themes.
- `Action Date`: date column for decision/action timing.
- `Action`: dropdown column for labels such as `Decision`.

Use `.env.example` as the local template.

## Local Development

This project uses Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then visit `http://localhost:8000/health`.

Run tests with:

```bash
pip install -r requirements-dev.txt
pytest
```

## Railway

Railway uses `railway.json` to start the app with Uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Add `MONDAY_API_TOKEN` and `TODO_BOARD_ID` as Railway environment variables before calling `POST /todos`.

Production health check:

```bash
curl https://timmeny-os-production.up.railway.app/health
```

Production todo test:

```bash
curl -X POST https://timmeny-os-production.up.railway.app/todos -H "Content-Type: application/json" -H "X-API-Key: $TIMMENY_OS_API_KEY" -d '{"title":"TEST - Railway Deploy"}'
```

Production GS todo test:

```bash
curl -X POST https://timmeny-os-production.up.railway.app/todos -H "Content-Type: application/json" -H "X-API-Key: $TIMMENY_OS_API_KEY" -d '{"title":"TEST - GS Railway Deploy","list":"gs"}'
```

Production decision todo test:

```bash
curl -X POST https://timmeny-os-production.up.railway.app/todos -H "Content-Type: application/json" -H "Authorization: Bearer $TIMMENY_OS_API_KEY" -d '{"title":"Decide launch owner","list":"todo","action_group":"Launch","action_date":"2026-06-21","action":"Decision"}'
```

## Naming

Product/app name: `Timmeny-ToDo-OS`

Current production URL:

```text
https://timmeny-os-production.up.railway.app
```

The URL can be renamed later in Railway after the service/domain rename is complete.

## Intent

Timmeny-ToDo-OS should make task capture easy to trust and easy to improve. The system should favor durable structure over clever one-offs, clear records over mystery state, and small useful loops over sprawling machinery.

## Principles

- **Legible by default:** important behavior should be understandable from the repo.
- **Local-first where practical:** personal data and working context should remain portable.
- **Automation with receipts:** automated actions should leave traceable outputs and decisions.
- **Human override:** workflows should help the operator think, not hide the controls.
- **Composable pieces:** prompts, scripts, notes, and agents should be easy to replace independently.

## Repository Map

- `main.py` contains the FastAPI app.
- `requirements.txt` defines the Python dependencies.
- `requirements-dev.txt` defines local test dependencies.
- `railway.json` configures Railway deployment.
- `docs/gpt-action-openapi.yaml` defines the GPT Action schema.
- `tests/` covers the current API surface.
- `docs/charter.md` defines the initial scope, values, and near-term direction.

## Next Steps

- Sketch the main workflows this system should support.
- Decide what belongs in code, docs, prompts, automations, or external tools.
- Add the next workflow only after the todo endpoint is working end to end.
