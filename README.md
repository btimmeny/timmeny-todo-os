# timmeny-os

A personal operating system for shaping work, decisions, automations, notes, and AI-assisted workflows into something coherent.

This repository starts as a lightweight FastAPI service plus a place to define the principles, interfaces, and routines that make the system useful before hardening more workflows.

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
  "title": "TEST - Railway"
}
```

Response:

```json
{
  "success": true,
  "item_id": "...",
  "title": "TEST - Railway"
}
```

## Configuration

Set these environment variables:

- `MONDAY_API_TOKEN`: Monday.com API token.
- `TODO_BOARD_ID`: Monday.com board id where todos should be created.

## Local Development

This project uses Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then visit `http://localhost:8000/health`.

## Railway

Railway uses `railway.json` to start the app with Uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Add `MONDAY_API_TOKEN` and `TODO_BOARD_ID` as Railway environment variables before calling `POST /todos`.

## Intent

Timmeny OS should make recurring work easier to trust and easier to improve. The system should favor durable structure over clever one-offs, clear records over mystery state, and small useful loops over sprawling machinery.

## Principles

- **Legible by default:** important behavior should be understandable from the repo.
- **Local-first where practical:** personal data and working context should remain portable.
- **Automation with receipts:** automated actions should leave traceable outputs and decisions.
- **Human override:** workflows should help the operator think, not hide the controls.
- **Composable pieces:** prompts, scripts, notes, and agents should be easy to replace independently.

## Repository Map

- `main.py` contains the FastAPI app.
- `requirements.txt` defines the Python dependencies.
- `railway.json` configures Railway deployment.
- `docs/charter.md` defines the initial scope, values, and near-term direction.

## Next Steps

- Sketch the main workflows this system should support.
- Decide what belongs in code, docs, prompts, automations, or external tools.
- Add the next workflow only after the todo endpoint is working end to end.
