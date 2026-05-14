from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, Union, runtime_checkable


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


Filter = Mapping[str, Any]


@runtime_checkable
class DatabaseAdapter(Protocol):
    def list_tables(self) -> List[str]:
        ...

    def table_schema(self, table: str) -> Dict[str, Any]:
        ...

    def database_schema(self) -> Dict[str, Any]:
        ...

    def search(
        self,
        table: str,
        filters: Optional[Sequence[Filter]] = None,
        columns: Optional[Sequence[str]] = None,
        limit: int = 20,
        offset: int = 0,
        order_by: Optional[str] = None,
        descending: bool = False,
    ) -> Dict[str, Any]:
        ...

    def insert(self, table: str, values: Mapping[str, Any]) -> Dict[str, Any]:
        ...

    def aggregate(
        self,
        table: str,
        metric: str,
        column: Optional[str] = None,
        filters: Optional[Sequence[Filter]] = None,
        group_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        ...


class SQLiteAdapter:
    SUPPORTED_OPERATORS = {
        "=": "=",
        "==": "=",
        "!=": "!=",
        "<>": "!=",
        "<": "<",
        "<=": "<=",
        ">": ">",
        ">=": ">=",
        "like": "LIKE",
        "in": "IN",
    }
    SUPPORTED_AGGREGATES = {"count", "avg", "sum", "min", "max"}

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def list_tables(self) -> List[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def table_schema(self, table: str) -> Dict[str, Any]:
        self._validate_table(table)
        with self.connect() as connection:
            rows = connection.execute(f"PRAGMA table_info({self._quote_identifier(table)})").fetchall()

        return {
            "table": table,
            "columns": [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "nullable": not bool(row["notnull"]),
                    "default": row["dflt_value"],
                    "primary_key": bool(row["pk"]),
                }
                for row in rows
            ],
        }

    def database_schema(self) -> Dict[str, Any]:
        return {"tables": {table: self.table_schema(table) for table in self.list_tables()}}

    def search(
        self,
        table: str,
        filters: Optional[Sequence[Filter]] = None,
        columns: Optional[Sequence[str]] = None,
        limit: int = 20,
        offset: int = 0,
        order_by: Optional[str] = None,
        descending: bool = False,
    ) -> Dict[str, Any]:
        self._validate_table(table)
        selected_columns = self._validate_selected_columns(table, columns)
        safe_limit = self._validate_limit(limit)
        safe_offset = self._validate_offset(offset)

        params: List[Any] = []
        where_clause, where_params = self._build_where_clause(table, filters)
        params.extend(where_params)

        order_clause = ""
        if order_by:
            self._validate_column(table, order_by)
            direction = "DESC" if descending else "ASC"
            order_clause = f" ORDER BY {self._quote_identifier(order_by)} {direction}"

        column_sql = ", ".join(self._quote_identifier(column) for column in selected_columns)
        sql = (
            f"SELECT {column_sql} FROM {self._quote_identifier(table)}"
            f"{where_clause}{order_clause} LIMIT {self._placeholder(len(params) + 1)} "
            f"OFFSET {self._placeholder(len(params) + 2)}"
        )
        params.extend([safe_limit, safe_offset])

        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(sql, params).fetchall()]

        return {
            "table": table,
            "columns": selected_columns,
            "filters": list(filters or []),
            "limit": safe_limit,
            "offset": safe_offset,
            "rows": rows,
        }

    def insert(self, table: str, values: Mapping[str, Any]) -> Dict[str, Any]:
        self._validate_table(table)
        if not values:
            raise ValidationError("Insert values cannot be empty")

        columns = list(values.keys())
        for column in columns:
            self._validate_column(table, column)

        placeholders = ", ".join(self._placeholder(index) for index, _ in enumerate(columns, start=1))
        column_sql = ", ".join(self._quote_identifier(column) for column in columns)
        sql = f"INSERT INTO {self._quote_identifier(table)} ({column_sql}) VALUES ({placeholders})"

        with self.connect() as connection:
            cursor = connection.execute(sql, [values[column] for column in columns])
            connection.commit()
            inserted_id = cursor.lastrowid

        row = dict(values)
        if "id" in self._column_names(table) and "id" not in row:
            row = {"id": inserted_id, **row}

        return {"table": table, "row": row}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: Optional[str] = None,
        filters: Optional[Sequence[Filter]] = None,
        group_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._validate_table(table)
        normalized_metric = metric.lower()
        if normalized_metric not in self.SUPPORTED_AGGREGATES:
            raise ValidationError(f"Unsupported aggregate: {metric}")

        if normalized_metric == "count":
            aggregate_target = "*"
            if column:
                self._validate_column(table, column)
                aggregate_target = self._quote_identifier(column)
        else:
            if not column:
                raise ValidationError(f"Aggregate '{normalized_metric}' requires a column")
            self._validate_column(table, column)
            aggregate_target = self._quote_identifier(column)

        params: List[Any] = []
        where_clause, where_params = self._build_where_clause(table, filters)
        params.extend(where_params)

        group_sql = ""
        select_group_sql = ""
        if group_by:
            self._validate_column(table, group_by)
            quoted_group = self._quote_identifier(group_by)
            select_group_sql = f"{quoted_group}, "
            group_sql = f" GROUP BY {quoted_group} ORDER BY {quoted_group} ASC"

        sql = (
            f"SELECT {select_group_sql}{normalized_metric.upper()}({aggregate_target}) AS value "
            f"FROM {self._quote_identifier(table)}{where_clause}{group_sql}"
        )

        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(sql, params).fetchall()]

        return {
            "table": table,
            "metric": normalized_metric,
            "column": column,
            "group_by": group_by,
            "filters": list(filters or []),
            "rows": rows,
        }

    def _build_where_clause(
        self, table: str, filters: Optional[Sequence[Filter]]
    ) -> Tuple[str, List[Any]]:
        if not filters:
            return "", []

        clauses: List[str] = []
        params: List[Any] = []
        for item in filters:
            column = item.get("column")
            operator = str(item.get("operator", "=")).lower()
            value = item.get("value")

            if not isinstance(column, str):
                raise ValidationError("Filter column must be a string")
            self._validate_column(table, column)
            if operator not in self.SUPPORTED_OPERATORS:
                raise ValidationError(f"Unsupported operator: {item.get('operator')}")

            sql_operator = self.SUPPORTED_OPERATORS[operator]
            if sql_operator == "IN":
                if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
                    raise ValidationError("IN filters require a list of values")
                value_list = list(value)
                if not value_list:
                    raise ValidationError("IN filters require at least one value")
                start = len(params) + 1
                placeholders = ", ".join(
                    self._placeholder(index)
                    for index in range(start, start + len(value_list))
                )
                clauses.append(f"{self._quote_identifier(column)} IN ({placeholders})")
                params.extend(value_list)
            else:
                clauses.append(
                    f"{self._quote_identifier(column)} {sql_operator} "
                    f"{self._placeholder(len(params) + 1)}"
                )
                params.append(value)

        return " WHERE " + " AND ".join(clauses), params

    def _validate_table(self, table: str) -> None:
        if not isinstance(table, str) or table not in self.list_tables():
            raise ValidationError(f"Unknown table: {table}")

    def _validate_column(self, table: str, column: str) -> None:
        if column not in self._column_names(table):
            raise ValidationError(f"Unknown column '{column}' for table '{table}'")

    def _validate_selected_columns(
        self, table: str, columns: Optional[Sequence[str]]
    ) -> List[str]:
        if columns is None:
            return self._column_names(table)
        if not columns:
            raise ValidationError("Selected columns cannot be empty")
        selected = list(columns)
        for column in selected:
            self._validate_column(table, column)
        return selected

    def _column_names(self, table: str) -> List[str]:
        with self.connect() as connection:
            rows = connection.execute(f"PRAGMA table_info({self._quote_identifier(table)})").fetchall()
        return [row["name"] for row in rows]

    @staticmethod
    def _validate_limit(limit: int) -> int:
        if not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValidationError("Limit must be an integer between 1 and 100")
        return limit

    @staticmethod
    def _validate_offset(offset: int) -> int:
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset must be a non-negative integer")
        return offset

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    @staticmethod
    def _placeholder(_position: int) -> str:
        return "?"


class PostgreSQLAdapter(SQLiteAdapter):
    """PostgreSQL implementation with the same MCP-facing adapter methods."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL support requires the optional `psycopg` package. "
                "Install it with `python -m pip install psycopg[binary]`."
            ) from exc
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def list_tables(self) -> List[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT table_name AS name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def table_schema(self, table: str) -> Dict[str, Any]:
        self._validate_table(table)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    column_name AS name,
                    data_type AS type,
                    is_nullable AS nullable,
                    column_default AS default,
                    ordinal_position
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                [table],
            ).fetchall()

        primary_keys = self._primary_key_columns(table)
        return {
            "table": table,
            "columns": [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "nullable": row["nullable"] == "YES",
                    "default": row["default"],
                    "primary_key": row["name"] in primary_keys,
                }
                for row in rows
            ],
        }

    def insert(self, table: str, values: Mapping[str, Any]) -> Dict[str, Any]:
        self._validate_table(table)
        if not values:
            raise ValidationError("Insert values cannot be empty")

        columns = list(values.keys())
        for column in columns:
            self._validate_column(table, column)

        placeholders = ", ".join(self._placeholder(index) for index, _ in enumerate(columns, start=1))
        column_sql = ", ".join(self._quote_identifier(column) for column in columns)
        sql = (
            f"INSERT INTO {self._quote_identifier(table)} ({column_sql}) "
            f"VALUES ({placeholders}) RETURNING *"
        )

        with self.connect() as connection:
            row = dict(connection.execute(sql, [values[column] for column in columns]).fetchone())
            connection.commit()

        return {"table": table, "row": row}

    def _column_names(self, table: str) -> List[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT column_name AS name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                [table],
            ).fetchall()
        return [row["name"] for row in rows]

    def _primary_key_columns(self, table: str) -> List[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT kcu.column_name AS name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                 AND tc.table_name = kcu.table_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = 'public'
                  AND tc.table_name = %s
                ORDER BY kcu.ordinal_position
                """,
                [table],
            ).fetchall()
        return [row["name"] for row in rows]

    @staticmethod
    def _placeholder(_position: int) -> str:
        return "%s"


def create_adapter(kind: str, **kwargs: Any) -> DatabaseAdapter:
    normalized = kind.lower().replace("-", "_")
    if normalized == "sqlite":
        db_path = kwargs.get("db_path")
        if not db_path:
            raise ValueError("sqlite adapter requires db_path")
        return SQLiteAdapter(db_path)
    if normalized in {"postgres", "postgresql"}:
        dsn = kwargs.get("dsn")
        if not dsn:
            raise ValueError("postgresql adapter requires dsn")
        return PostgreSQLAdapter(dsn)
    raise ValueError(f"Unsupported database adapter: {kind}")
