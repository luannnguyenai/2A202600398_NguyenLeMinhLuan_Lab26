from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional, Union


DEFAULT_DB_PATH = Path(__file__).with_name("lab.sqlite")


SCHEMA_SQL = """
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100)
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'dropped')),
    grade REAL CHECK (grade IS NULL OR (grade >= 0 AND grade <= 100)),
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);
"""


SEED_SQL = """
INSERT INTO students (name, cohort, score) VALUES
    ('Alice Nguyen', 'A1', 88.5),
    ('Ben Smith', 'B2', 92.0),
    ('Cara Chen', 'A1', 95.0),
    ('Diego Patel', 'A1', 80.5),
    ('Eve Garcia', 'B2', 79.5);

INSERT INTO courses (code, title, credits) VALUES
    ('MCP101', 'Model Context Protocol Foundations', 3),
    ('SQL201', 'Practical SQLite', 4),
    ('AI305', 'Applied AI Systems', 3);

INSERT INTO enrollments (student_id, course_id, status, grade) VALUES
    (1, 1, 'completed', 90.0),
    (1, 2, 'active', NULL),
    (2, 1, 'completed', 93.0),
    (3, 3, 'active', NULL),
    (4, 2, 'completed', 82.0),
    (5, 1, 'dropped', NULL);
"""


def create_database(path: Optional[Union[str, Path]] = None) -> Path:
    """Create a reproducible SQLite database and return its path."""
    db_path = Path(path) if path is not None else DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_SQL)
        connection.executescript(SEED_SQL)
        connection.commit()

    return db_path


if __name__ == "__main__":
    print(create_database())
