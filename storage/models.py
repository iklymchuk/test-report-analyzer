"""
SQLAlchemy ORM models for test report data.

This module defines the database schema for storing test runs and test cases.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from storage.database import Base


class TestRun(Base):
    """
    Represents a complete test run (e.g., one CI pipeline execution).

    A test run contains multiple test cases and tracks aggregate metrics
    like total tests, pass/fail counts, and overall duration.

    Attributes:
        id: Primary key
        timestamp: When the test run occurred
        project: Project name (e.g., "my-app", "backend-api")
        branch: Git branch name (e.g., "main", "feature/new-feature")
        commit_sha: Git commit hash
        duration_seconds: Total time to run all tests
        total_tests: Total number of tests executed
        passed: Number of tests that passed
        failed: Number of tests that failed
        skipped: Number of tests that were skipped
        status: Overall status (e.g., "success", "failure")
        created_at: When this record was created in the database
    """

    __tablename__ = "test_runs"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Test run metadata
    timestamp = Column(DateTime, nullable=False, index=True)
    project = Column(String(255), nullable=False, index=True)
    branch = Column(String(255), index=True)
    commit_sha = Column(String(40))

    # Aggregate metrics
    duration_seconds = Column(Float)
    total_tests = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    status = Column(String(20))

    # Audit field
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    test_cases = relationship(
        "TestCase",
        back_populates="test_run",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Composite indexes for common queries
    __table_args__ = (
        Index("idx_project_timestamp", "project", "timestamp"),
        Index("idx_project_branch", "project", "branch"),
    )

    def __repr__(self):
        return (
            f"<TestRun(id={self.id}, project='{self.project}', "
            f"timestamp={self.timestamp}, total_tests={self.total_tests}, "
            f"failed={self.failed})>"
        )

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return round((self.passed / self.total_tests) * 100, 2)

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return round((self.failed / self.total_tests) * 100, 2)


class TestCase(Base):
    """
    Represents an individual test case within a test run.

    Each test case tracks its execution result, duration, and any error
    information if the test failed.

    Attributes:
        id: Primary key
        test_run_id: Foreign key to the parent test run
        name: Test name (e.g., "test_login_with_valid_credentials")
        classname: Test class or module (e.g., "tests.auth.test_login")
        duration_seconds: Time taken to execute this test
        status: Test result (passed, failed, error, skipped)
        error_message: Full error message/stack trace if test failed
        error_type: Type of error (e.g., "AssertionError", "TimeoutError")
        stdout: Standard output captured during test
        stderr: Standard error captured during test
        created_at: When this record was created in the database
    """

    __tablename__ = "test_cases"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to test run
    test_run_id = Column(
        Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False
    )

    # Test identification
    name = Column(String(500), nullable=False)
    classname = Column(String(500))

    # Execution metrics
    duration_seconds = Column(Float)
    status = Column(String(20), nullable=False)  # passed, failed, error, skipped

    # Error information (if failed)
    error_message = Column(Text)
    error_type = Column(String(255))

    # Output capture (optional)
    stdout = Column(Text)
    stderr = Column(Text)

    # Audit field
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    test_run = relationship("TestRun", back_populates="test_cases")

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_test_run", "test_run_id"),
        Index("idx_name_status", "name", "status"),
        Index("idx_classname", "classname"),
        Index("idx_status", "status"),
    )

    def __repr__(self):
        return (
            f"<TestCase(id={self.id}, name='{self.name}', "
            f"status='{self.status}', duration={self.duration_seconds}s)>"
        )

    @property
    def full_name(self) -> str:
        """Get fully qualified test name."""
        if self.classname:
            return f"{self.classname}::{self.name}"
        return self.name

    @property
    def is_failed(self) -> bool:
        """Check if test failed."""
        return self.status in ["failed", "error"]

    @property
    def is_passed(self) -> bool:
        """Check if test passed."""
        return self.status == "passed"

    @property
    def is_slow(self, threshold: float = 5.0) -> bool:
        """Check if test is slow (above threshold)."""
        return self.duration_seconds is not None and self.duration_seconds > threshold
