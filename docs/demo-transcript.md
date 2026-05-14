# Demo Transcript

This transcript was produced with:

```bash
.venv312/bin/python implementation/verify_server.py
```

## What It Demonstrates

- Database initialization
- Tool discovery for `search`, `insert`, and `aggregate`
- Resource discovery for `schema://database`
- Resource template discovery for `schema://table/{table_name}`
- Successful search, insert, and aggregate calls
- Successful table schema read
- Clear invalid request error for a missing table
- HTTP bearer auth rejects missing or wrong tokens and accepts a valid token

## Key Output

```text
## mcp tools
[
  "aggregate",
  "insert",
  "search"
]

## mcp resources
[
  "schema://database"
]

## mcp resource templates
[
  "schema://table/{table_name}"
]

## mcp valid tool call
{
  "table": "students",
  "columns": [
    "name",
    "cohort"
  ],
  "filters": [
    {
      "column": "cohort",
      "operator": "=",
      "value": "A1"
    }
  ],
  "limit": 1,
  "offset": 0,
  "rows": [
    {
      "name": "Alice Nguyen",
      "cohort": "A1"
    }
  ]
}

## mcp invalid tool call
{
  "ok": false,
  "error": "Unknown table: missing"
}

## http bearer auth demo
{
  "missing_token_status": 401,
  "missing_token_body": {
    "ok": false,
    "error": "Missing bearer token"
  },
  "wrong_token_status": 403,
  "wrong_token_body": {
    "ok": false,
    "error": "Invalid bearer token"
  },
  "valid_token_status": 405,
  "valid_token_body": "Method Not Allowed"
}

Verification completed.
```

## Codex Client Configuration Check

The Codex CLI was available locally and a disposable project-local config was verified with:

```bash
mkdir -p .codex-local
CODEX_HOME="$PWD/.codex-local" codex mcp add sqlite-lab -- "$PWD/.venv312/bin/python" "$PWD/implementation/mcp_server.py"
CODEX_HOME="$PWD/.codex-local" codex mcp list
```

Expected listing:

```text
Name        Command                 Args                                  Status
sqlite-lab  .../.venv312/bin/python .../implementation/mcp_server.py      enabled
```
