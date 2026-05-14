# MCP Inspector Screenshot Set

Use these screenshots as codelab evidence:

- `02-inspector-connected.png` - server connected successfully.
- `03-resources-and-templates.png` - `schema://database` resource and `schema://table/{table_name}` template are discoverable.
- `04-tools-discovered.png` - `search`, `insert`, and `aggregate` tools are discoverable.
- `06-valid-search-result.png` - valid `search` tool call returns student rows.
- `07-invalid-search-error.png` - invalid table request returns a clear error payload.
- `08-database-schema-resource.png` - full database schema resource is readable.
- `09-table-schema-resource.png` - per-table `schema://table/students` resource template is readable.
- `10-valid-aggregate-call.png` - valid `aggregate` call returns an average score.
- `11-valid-insert-call.png` - valid `insert` call succeeds with the inserted payload input visible.

The Inspector was launched with:

```bash
./implementation/start_inspector.sh
```
