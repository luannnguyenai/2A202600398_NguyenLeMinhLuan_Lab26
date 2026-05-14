# SQLite Lab MCP Server

FastMCP server backed by SQLite for the Day 26 Track 3 MCP tool integration lab. It exposes the required MCP tools and schema resources:

- `search`
- `insert`
- `aggregate`
- `schema://database`
- `schema://table/{table_name}`

The implementation uses parameterized SQL values, validates table and column identifiers against SQLite metadata, and rejects unsupported operators, bad aggregate requests, unknown identifiers, and empty inserts.

Bonus support is included for bearer-token auth on HTTP/SSE transports and a PostgreSQL adapter behind the same database interface.

## Project Structure

```text
implementation/
  auth.py             # bearer-token middleware for HTTP/SSE demos
  db.py               # SQLite adapter, validation, SQL construction
  init_db.py          # reproducible schema and seed data
  mcp_server.py       # FastMCP server, tools, resources
  verify_server.py    # repeatable MCP smoke verification
  start_inspector.sh  # MCP Inspector helper
  tests/
    test_db.py        # automated behavior and safety tests
examples/
  claude.mcp.json
  codex-config.toml
  gemini-settings.json
docs/
  demo-transcript.md
```

## Requirements

- Python 3.10 or newer
- FastMCP
- pytest for tests
- Optional: Codex, Claude Code, Gemini CLI, or MCP Inspector for manual client checks
- Optional: PostgreSQL plus `psycopg[binary]` for the PostgreSQL adapter

Python 3.12 was used for local FastMCP verification.

## Setup

Using `uv`:

```bash
UV_CACHE_DIR=.uv-cache uv venv .venv312 --python 3.12
UV_CACHE_DIR=.uv-cache uv pip install --python .venv312/bin/python -r requirements.txt
```

Using an existing Python 3.10+ interpreter:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Initialize or reset the SQLite database:

```bash
.venv312/bin/python implementation/init_db.py
```

The server also creates `implementation/lab.sqlite` automatically if it is missing.

## Run The Server

```bash
.venv312/bin/python implementation/mcp_server.py
```

The default transport is stdio, which is the easiest local workflow for MCP clients.

Run HTTP transport with bearer-token auth:

```bash
MCP_AUTH_TOKEN=demo-token .venv312/bin/python implementation/mcp_server.py --transport http --host 127.0.0.1 --port 8000 --path /mcp
```

Run SSE transport with the same auth middleware:

```bash
MCP_AUTH_TOKEN=demo-token .venv312/bin/python implementation/mcp_server.py --transport sse --host 127.0.0.1 --port 8000
```

HTTP/SSE clients must send:

```text
Authorization: Bearer demo-token
```

Missing tokens return `401`; wrong tokens return `403`. A valid token reaches the FastMCP HTTP/SSE app.

## Tools

### `search`

Search rows with validated filters, selected columns, ordering, limit, and offset.

Example arguments:

```json
{
  "table": "students",
  "filters": [{"column": "cohort", "operator": "=", "value": "A1"}],
  "columns": ["name", "cohort", "score"],
  "order_by": "score",
  "descending": true,
  "limit": 2,
  "offset": 0
}
```

Supported operators: `=`, `==`, `!=`, `<>`, `<`, `<=`, `>`, `>=`, `like`, `in`.

### `insert`

Insert one row into a known table and return the inserted payload, including generated `id` when present.

Example arguments:

```json
{
  "table": "students",
  "values": {"name": "Linh Tran", "cohort": "C3", "score": 91.25}
}
```

### `aggregate`

Run `count`, `avg`, `sum`, `min`, or `max`, with optional filters and grouping.

Example arguments:

```json
{
  "table": "students",
  "metric": "avg",
  "column": "score",
  "group_by": "cohort"
}
```

## Resources

- `schema://database` returns the full database schema as JSON.
- `schema://table/{table_name}` returns one validated table schema as JSON.

Example:

```text
schema://table/students
```

## Testing And Verification

Run automated tests:

```bash
.venv312/bin/python -m pytest
```

Run the end-to-end smoke verification:

```bash
.venv312/bin/python implementation/verify_server.py
```

The verification script checks:

- database initialization
- valid `search`, `insert`, and `aggregate` calls
- invalid request error handling
- MCP tool discovery
- MCP resource discovery
- MCP resource template discovery
- MCP schema reads
- HTTP bearer auth failure and success behavior

Validation failures from MCP tools return a structured payload such as `{"ok": false, "error": "Unknown table: missing"}`.

A saved sample transcript is in [docs/demo-transcript.md](docs/demo-transcript.md).

## MCP Inspector

```bash
chmod +x implementation/start_inspector.sh
./implementation/start_inspector.sh
```

Inspector checklist:

- tools show `search`, `insert`, and `aggregate`
- resources show `schema://database`
- resource templates show `schema://table/{table_name}`
- valid calls return rows
- invalid calls return clear errors

## Client Examples

Example config files are in [examples](examples).

### Codex

Temporary project-local verification:

```bash
mkdir -p .codex-local
CODEX_HOME="$PWD/.codex-local" codex mcp add sqlite-lab -- "$PWD/.venv312/bin/python" "$PWD/implementation/mcp_server.py"
CODEX_HOME="$PWD/.codex-local" codex mcp list
```

Expected result: `sqlite-lab` appears with status `enabled`.

Permanent config shape:

```toml
[mcp_servers.sqlite-lab]
command = "/ABSOLUTE/PATH/TO/.venv312/bin/python"
args = ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"]
```

### Claude Code

Use [examples/claude.mcp.json](examples/claude.mcp.json), replacing paths with absolute paths for your checkout.

### Gemini CLI

Command form:

```bash
gemini mcp add sqlite-lab "$PWD/.venv312/bin/python" "$PWD/implementation/mcp_server.py" --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
```

Settings fragment: [examples/gemini-settings.json](examples/gemini-settings.json).

## PostgreSQL Mode

SQLite is the default. PostgreSQL uses the same MCP tool/resource surface through `PostgreSQLAdapter`.

Install PostgreSQL support:

```bash
.venv312/bin/python -m pip install "psycopg[binary]>=3.2.0"
```

Run against PostgreSQL:

```bash
MCP_DB_BACKEND=postgresql \
DATABASE_URL="postgresql://user:password@localhost:5432/database" \
.venv312/bin/python implementation/mcp_server.py
```

The PostgreSQL adapter validates public-schema tables and columns through `information_schema`, uses `%s` bound parameters, and returns inserted rows with `RETURNING *`.

## Bonus Verification

Bonus checks are included in the regular test suite:

```bash
.venv312/bin/python -m pytest implementation/tests/test_bonus.py
```

That test verifies:

- bearer-token middleware blocks missing and invalid tokens
- valid bearer tokens pass through
- the adapter factory returns SQLite and PostgreSQL adapters behind the shared `DatabaseAdapter` protocol

## Demo Tasks

Use these prompts or Inspector calls:

- Search all students in cohort `A1`.
- Insert a new student.
- Count rows in `students`.
- Compute average student score by cohort.
- Read `schema://database`.
- Read `schema://table/students`.
- Try searching table `missing` and confirm the clear validation error.

## Safety Notes

SQL identifiers are accepted only after checking live SQLite schema metadata. User values are passed as bound parameters. Filters and aggregates are restricted to known operators and metrics, and pagination limits are capped at 100 rows.
