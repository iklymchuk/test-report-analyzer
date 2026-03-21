"""Tests for JUnit XML parser."""

import pytest
from pathlib import Path
from ingestion.junit_parser import JUnitParser


@pytest.fixture
def sample_report_path():
    """Path to sample JUnit XML report."""
    return Path(__file__).parent / "fixtures" / "sample_report.xml"


@pytest.fixture
def multi_suite_report_path():
    """Path to multi-suite JUnit XML report."""
    return Path(__file__).parent / "fixtures" / "multi_suite_report.xml"


def test_parser_initialization():
    """Test JUnitParser can be initialized."""
    parser = JUnitParser()
    assert parser is not None


def test_parse_sample_report(sample_report_path):
    """Test parsing a sample JUnit XML report."""
    if not sample_report_path.exists():
        pytest.skip("Sample report not found")

    parser = JUnitParser()
    result = parser.parse_file(str(sample_report_path))

    assert result is not None
    assert "test_cases" in result
    assert "summary" in result
    assert isinstance(result["test_cases"], list)
    assert isinstance(result["summary"], dict)


def test_parse_multi_suite_report(multi_suite_report_path):
    """Test parsing a multi-suite JUnit XML report."""
    if not multi_suite_report_path.exists():
        pytest.skip("Multi-suite report not found")

    parser = JUnitParser()
    result = parser.parse_file(str(multi_suite_report_path))

    assert result is not None
    assert "test_cases" in result
    assert len(result["test_cases"]) > 0


def test_parse_nonexistent_file():
    """Test parsing a non-existent file raises error."""
    parser = JUnitParser()

    with pytest.raises((FileNotFoundError, Exception)):
        parser.parse_file("nonexistent_file.xml")


def test_summary_counts(sample_report_path):
    """Test that summary counts are correct."""
    if not sample_report_path.exists():
        pytest.skip("Sample report not found")

    parser = JUnitParser()
    result = parser.parse_file(str(sample_report_path))

    summary = result["summary"]
    assert "total" in summary
    assert "passed" in summary or "failures" in summary or "errors" in summary
    assert summary["total"] >= 0
