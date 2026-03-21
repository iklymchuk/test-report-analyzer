"""Tests for database models."""

import pytest
from datetime import datetime
from storage.models import TestRun, TestCase


def test_test_run_model_creation():
    """Test TestRun model can be instantiated."""
    run = TestRun(
        project="test-project",
        branch="main",
        commit_sha="abc123",
        timestamp=datetime.now(),
        total_tests=10,
        passed_tests=8,
        failed_tests=1,
        skipped_tests=1,
        duration_seconds=45.5,
        status="completed",
    )

    # Verify the object was created
    assert run is not None
    assert hasattr(run, "project")
    assert hasattr(run, "branch")
    assert hasattr(run, "commit_sha")
    assert hasattr(run, "total_tests")


def test_test_case_model_creation():
    """Test TestCase model can be instantiated."""
    test_case = TestCase(
        test_run_id=1,
        name="test_example",
        classname="TestClass",
        status="passed",
        duration_seconds=1.5,
        file_path="tests/test_example.py",
    )

    # Verify the object was created
    assert test_case is not None
    assert hasattr(test_case, "test_run_id")
    assert hasattr(test_case, "name")
    assert hasattr(test_case, "classname")
    assert hasattr(test_case, "status")


def test_test_case_with_error_information():
    """Test TestCase model can store error information."""
    test_case = TestCase(
        test_run_id=1,
        name="test_failing",
        classname="TestClass",
        status="failed",
        duration_seconds=2.0,
        error_message="AssertionError: Expected 1 but got 2",
        error_type="AssertionError",
    )

    # Verify error fields exist
    assert test_case is not None
    assert hasattr(test_case, "error_message")
    assert hasattr(test_case, "error_type")


def test_models_can_be_imported():
    """Test that model classes can be imported."""
    from storage.models import TestRun, TestCase, Base

    assert TestRun is not None
    assert TestCase is not None
    assert Base is not None
