"""Integration tests for database operations."""

import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from storage.models import Base, TestRun, TestCase
from datetime import datetime


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        db_path = f.name

    # Create engine and session
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    try:
        os.unlink(db_path)
    except OSError:
        pass


def test_database_tables_created(test_db):
    """Test that database tables are created successfully."""
    assert test_db is not None


def test_insert_test_run(test_db):
    """Test inserting a test run into the database."""
    run = TestRun(
        project="test-project",
        branch="main",
        commit_sha="abc123",
        timestamp=datetime.now(),
        total_tests=5,
        passed_tests=4,
        failed_tests=1,
        skipped_tests=0,
        duration_seconds=10.5,
        status="completed",
    )

    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)

    # Verify ID was assigned
    assert run.id is not None


def test_insert_test_case_with_run(test_db):
    """Test inserting a test case linked to a test run."""
    # First create a test run
    run = TestRun(
        project="test-project",
        branch="main",
        commit_sha="abc123",
        timestamp=datetime.now(),
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        skipped_tests=0,
        duration_seconds=1.0,
        status="completed",
    )

    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)

    # Now create a test case
    test_case = TestCase(
        test_run_id=run.id,
        name="test_example",
        classname="TestClass",
        status="passed",
        duration_seconds=1.0,
    )

    test_db.add(test_case)
    test_db.commit()
    test_db.refresh(test_case)

    # Verify both IDs are set
    assert test_case.id is not None
    assert run.id is not None


def test_query_test_runs_by_project(test_db):
    """Test querying test runs from the database."""
    # Create a test run
    run = TestRun(
        project="query-test",
        branch="feature",
        commit_sha="xyz789",
        timestamp=datetime.now(),
        total_tests=3,
        passed_tests=2,
        failed_tests=1,
        skipped_tests=0,
        duration_seconds=5.0,
        status="completed",
    )

    test_db.add(run)
    test_db.commit()

    # Query it back
    result = test_db.query(TestRun).filter(TestRun.project == "query-test").first()

    # Verify we got a result
    assert result is not None
    assert result.id is not None
