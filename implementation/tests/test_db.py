import pytest

from implementation.db import SQLiteAdapter, ValidationError
from implementation.init_db import create_database


@pytest.fixture()
def adapter(tmp_path):
    db_path = create_database(tmp_path / "lab.sqlite")
    return SQLiteAdapter(db_path)


def test_search_filters_orders_and_paginates(adapter):
    result = adapter.search(
        table="students",
        filters=[{"column": "cohort", "operator": "=", "value": "A1"}],
        columns=["name", "cohort", "score"],
        order_by="score",
        descending=True,
        limit=2,
        offset=0,
    )

    assert result["table"] == "students"
    assert result["limit"] == 2
    assert [row["name"] for row in result["rows"]] == ["Cara Chen", "Alice Nguyen"]
    assert all(row["cohort"] == "A1" for row in result["rows"])


def test_insert_returns_inserted_payload_with_generated_id(adapter):
    inserted = adapter.insert(
        "students",
        {"name": "Linh Tran", "cohort": "C3", "score": 91.25},
    )

    assert inserted["table"] == "students"
    assert inserted["row"]["id"] > 0
    assert inserted["row"]["name"] == "Linh Tran"
    assert inserted["row"]["cohort"] == "C3"
    assert inserted["row"]["score"] == 91.25

    found = adapter.search(
        "students",
        filters=[{"column": "id", "operator": "=", "value": inserted["row"]["id"]}],
    )
    assert found["rows"] == [inserted["row"]]


def test_aggregate_supports_count_avg_and_group_by(adapter):
    count = adapter.aggregate("students", "count")
    assert count["rows"] == [{"value": 5}]

    averages = adapter.aggregate("students", "avg", column="score", group_by="cohort")
    assert averages["rows"] == [
        {"cohort": "A1", "value": 88.0},
        {"cohort": "B2", "value": 85.75},
    ]


def test_schema_resources_are_serializable(adapter):
    full_schema = adapter.database_schema()
    table_schema = adapter.table_schema("students")

    assert set(full_schema["tables"]) == {"students", "courses", "enrollments"}
    assert [column["name"] for column in table_schema["columns"]] == [
        "id",
        "name",
        "cohort",
        "score",
    ]


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda db: db.search("missing"), "Unknown table"),
        (lambda db: db.search("students", columns=["password"]), "Unknown column"),
        (
            lambda db: db.search(
                "students",
                filters=[{"column": "score", "operator": "contains", "value": "9"}],
            ),
            "Unsupported operator",
        ),
        (lambda db: db.insert("students", {}), "Insert values cannot be empty"),
        (lambda db: db.aggregate("students", "median", column="score"), "Unsupported aggregate"),
        (lambda db: db.aggregate("students", "avg"), "requires a column"),
    ],
)
def test_invalid_requests_raise_clear_validation_errors(adapter, call, message):
    with pytest.raises(ValidationError, match=message):
        call(adapter)
