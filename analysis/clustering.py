"""
Failure Clustering Module.

This module groups test failures by error patterns to identify systemic issues
and common root causes. This helps teams prioritize fixes by addressing
clusters of failures rather than individual tests.

Clustering approaches:
- Error type grouping
- Error message pattern matching
- Module/package-based clustering
- Temporal clustering (failures in same time window)
"""

from typing import List, Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta
import re
from sqlalchemy.orm import Session
from sqlalchemy import desc

from storage.models import TestRun, TestCase


def cluster_failures(
    db: Session, project: str, lookback_days: int = 7, min_cluster_size: int = 2
) -> List[Dict]:
    """
    Group failures by error message patterns.

    Identifies common error patterns across multiple test failures to help
    teams understand systemic issues rather than treating each failure independently.

    Args:
        db: Database session
        project: Project name
        lookback_days: Number of days to look back
        min_cluster_size: Minimum number of failures to form a cluster

    Returns:
        List of failure clusters sorted by size

    Example:
        ```python
        db = SessionLocal()
        clusters = cluster_failures(db, "my-app", lookback_days=14)

        for cluster in clusters:
            print(f"Pattern: {cluster['pattern']}")
            print(f"  Affected tests: {cluster['count']}")
        ```
    """
    # Get recent failures
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    failures = (
        db.query(TestCase, TestRun)
        .join(TestRun)
        .filter(
            TestRun.project == project,
            TestRun.timestamp >= cutoff,
            TestCase.status.in_(["failed", "error"]),
        )
        .order_by(desc(TestRun.timestamp))
        .all()
    )

    if not failures:
        return []

    # Cluster by error pattern
    clusters = defaultdict(list)

    for case, run in failures:
        # Extract error pattern
        pattern = _extract_error_pattern(case.error_message, case.error_type)

        clusters[pattern].append(
            {
                "test": _make_test_key(case.classname, case.name),
                "error_message": (
                    case.error_message[:500] if case.error_message else ""
                ),  # Truncate
                "error_type": case.error_type,
                "timestamp": run.timestamp.isoformat(),
                "duration": case.duration_seconds,
            }
        )

    # Format results
    result = []

    for pattern, failure_list in clusters.items():
        if len(failure_list) < min_cluster_size:
            continue

        # Get unique tests affected
        unique_tests = list(set(f["test"] for f in failure_list))

        # Calculate time span
        timestamps = [datetime.fromisoformat(f["timestamp"]) for f in failure_list]
        first_occurrence = min(timestamps)
        last_occurrence = max(timestamps)

        result.append(
            {
                "pattern": pattern,
                "count": len(failure_list),
                "unique_tests": len(unique_tests),
                "affected_tests": unique_tests[:10],  # Top 10
                "sample_error": failure_list[0]["error_message"],
                "error_type": failure_list[0]["error_type"],
                "first_occurrence": first_occurrence.isoformat(),
                "last_occurrence": last_occurrence.isoformat(),
                "occurrences": sorted(
                    failure_list, key=lambda x: x["timestamp"], reverse=True
                )[:5],
            }
        )

    return sorted(result, key=lambda x: x["count"], reverse=True)


def cluster_by_module(db: Session, project: str, lookback_days: int = 7) -> List[Dict]:
    """
    Group failures by module/package.

    Identifies which parts of the codebase have the most failures,
    useful for identifying problematic modules or recent changes.

    Args:
        db: Database session
        project: Project name
        lookback_days: Number of days to look back

    Returns:
        List of modules with failure counts
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    failures = (
        db.query(TestCase, TestRun)
        .join(TestRun)
        .filter(
            TestRun.project == project,
            TestRun.timestamp >= cutoff,
            TestCase.status.in_(["failed", "error"]),
            TestCase.classname.isnot(None),
        )
        .all()
    )

    if not failures:
        return []

    # Group by module (extract package from classname)
    module_failures = defaultdict(list)

    for case, run in failures:
        module = _extract_module(case.classname)

        module_failures[module].append(
            {
                "test": _make_test_key(case.classname, case.name),
                "error_type": case.error_type,
                "timestamp": run.timestamp.isoformat(),
            }
        )

    # Format results
    result = []
    for module, failure_list in module_failures.items():
        unique_tests = list(set(f["test"] for f in failure_list))

        # Count error types
        error_types = defaultdict(int)
        for f in failure_list:
            if f["error_type"]:
                error_types[f["error_type"]] += 1

        result.append(
            {
                "module": module,
                "total_failures": len(failure_list),
                "unique_tests": len(unique_tests),
                "affected_tests": unique_tests[:5],
                "error_types": dict(error_types),
                "most_common_error": (
                    max(error_types.items(), key=lambda x: x[1])[0]
                    if error_types
                    else None
                ),
            }
        )

    return sorted(result, key=lambda x: x["total_failures"], reverse=True)


def cluster_by_time(
    db: Session, project: str, lookback_days: int = 7, window_hours: int = 1
) -> List[Dict]:
    """
    Detect failure spikes (clusters of failures in time windows).

    Useful for identifying sudden issues caused by deployments,
    infrastructure problems, or environment changes.

    Args:
        db: Database session
        project: Project name
        lookback_days: Number of days to analyze
        window_hours: Time window size for clustering

    Returns:
        List of time windows with elevated failure rates
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    # Get all test runs in the period
    runs = (
        db.query(TestRun)
        .filter(TestRun.project == project, TestRun.timestamp >= cutoff)
        .order_by(TestRun.timestamp)
        .all()
    )

    if not runs:
        return []

    # Group runs into time windows
    window_delta = timedelta(hours=window_hours)
    windows = defaultdict(list)

    for run in runs:
        # Round timestamp to window
        window_start = run.timestamp.replace(minute=0, second=0, microsecond=0)
        # Adjust to window boundary
        hours_offset = (run.timestamp.hour // window_hours) * window_hours
        window_start = window_start.replace(hour=hours_offset)

        windows[window_start].append(run)

    # Calculate statistics for each window
    result = []

    for window_start, window_runs in windows.items():
        if not window_runs:
            continue

        total_tests = sum(r.total_tests for r in window_runs if r.total_tests)
        total_failures = sum(r.failed for r in window_runs if r.failed)

        if total_tests == 0:
            continue

        failure_rate = (total_failures / total_tests * 100) if total_tests > 0 else 0

        result.append(
            {
                "window_start": window_start.isoformat(),
                "window_end": (window_start + window_delta).isoformat(),
                "test_runs": len(window_runs),
                "total_tests": total_tests,
                "total_failures": total_failures,
                "failure_rate": round(failure_rate, 2),
                "avg_duration": round(
                    sum(r.duration_seconds for r in window_runs if r.duration_seconds)
                    / len(window_runs),
                    2,
                ),
            }
        )

    # Flag windows with high failure rates
    if result:
        avg_failure_rate = sum(r["failure_rate"] for r in result) / len(result)

        for window in result:
            window["is_spike"] = window["failure_rate"] > avg_failure_rate * 2

    return sorted(result, key=lambda x: x["failure_rate"], reverse=True)


def find_related_failures(
    db: Session,
    test_name: str,
    project: str,
    lookback_days: int = 7,
    similarity_threshold: float = 0.5,
) -> List[Dict]:
    """
    Find other tests failing with similar errors.

    Useful for understanding if a test failure is isolated or part of
    a broader issue affecting multiple tests.

    Args:
        db: Database session
        test_name: Test to find related failures for
        project: Project name
        lookback_days: Days to look back
        similarity_threshold: Minimum similarity score (0-1)

    Returns:
        List of related failing tests
    """
    # Parse test name
    if "::" in test_name:
        classname, name = test_name.split("::", 1)
    else:
        classname = None
        name = test_name

    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    # Get failures for the target test
    query = (
        db.query(TestCase, TestRun)
        .join(TestRun)
        .filter(
            TestRun.project == project,
            TestRun.timestamp >= cutoff,
            TestCase.name == name,
            TestCase.status.in_(["failed", "error"]),
        )
    )

    if classname:
        query = query.filter(TestCase.classname == classname)

    target_failures = query.all()

    if not target_failures:
        return []

    # Get error patterns from target test
    target_patterns = [
        _extract_error_pattern(case.error_message, case.error_type)
        for case, _ in target_failures
    ]

    if not target_patterns:
        return []

    # Find other failures with similar patterns
    all_failures = (
        db.query(TestCase, TestRun)
        .join(TestRun)
        .filter(
            TestRun.project == project,
            TestRun.timestamp >= cutoff,
            TestCase.status.in_(["failed", "error"]),
        )
        .all()
    )

    related = []
    seen_tests = set()

    for case, run in all_failures:
        test_key = _make_test_key(case.classname, case.name)

        # Skip the original test
        if test_key == test_name:
            continue

        # Skip if already seen
        if test_key in seen_tests:
            continue

        # Check if error pattern matches
        error_pattern = _extract_error_pattern(case.error_message, case.error_type)

        if error_pattern in target_patterns:
            seen_tests.add(test_key)

            related.append(
                {
                    "test": test_key,
                    "error_pattern": error_pattern,
                    "error_type": case.error_type,
                    "sample_error": (
                        case.error_message[:200] if case.error_message else ""
                    ),
                    "timestamp": run.timestamp.isoformat(),
                }
            )

    return related


def _extract_error_pattern(
    error_message: Optional[str], error_type: Optional[str]
) -> str:
    """
    Extract normalized error pattern for clustering.

    Removes specific values (numbers, paths, etc.) to create a pattern
    that matches similar errors across different test runs.
    """
    if not error_message:
        return error_type or "Unknown Error"

    # Extract first line (usually most informative)
    lines = error_message.split("\n")
    first_line = lines[0] if lines else error_message

    # Common normalizations
    pattern = first_line

    # Replace numbers with placeholder
    pattern = re.sub(r"\b\d+\b", "N", pattern)

    # Replace file paths (Unix-style)
    pattern = re.sub(r"/[\w/\-.]+/", "/PATH/", pattern)
    # Replace file paths (Windows-style)
    pattern = re.sub(r"\\[\w\\\-.]+\\", "WINPATH", pattern)

    # Replace hex addresses
    pattern = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", pattern)

    # Replace UUIDs
    pattern = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "UUID",
        pattern,
        flags=re.IGNORECASE,
    )

    # Replace timestamps
    pattern = re.sub(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}", "TIMESTAMP", pattern)

    # Truncate to reasonable length
    pattern = pattern[:150]

    # Prepend error type if available
    if error_type:
        return f"{error_type}: {pattern}"

    return pattern


def _extract_module(classname: str) -> str:
    """
    Extract module/package name from classname.

    Examples:
        'tests.api.test_auth' -> 'tests.api'
        'com.example.TestClass' -> 'com.example'
    """
    if not classname:
        return "unknown"

    parts = classname.split(".")

    # Take all but the last part (which is usually the class)
    if len(parts) > 1:
        return ".".join(parts[:-1])

    return classname


def _make_test_key(classname: Optional[str], name: str) -> str:
    """Create unique test identifier."""
    if classname:
        return f"{classname}::{name}"
    return name


def get_failure_summary(db: Session, project: str, lookback_days: int = 7) -> Dict:
    """
    Get high-level summary of failure patterns.

    Args:
        db: Database session
        project: Project name
        lookback_days: Days to analyze

    Returns:
        Summary statistics about failures
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    # Get all failures
    failures = (
        db.query(TestCase)
        .join(TestRun)
        .filter(
            TestRun.project == project,
            TestRun.timestamp >= cutoff,
            TestCase.status.in_(["failed", "error"]),
        )
        .all()
    )

    if not failures:
        return {
            "project": project,
            "period_days": lookback_days,
            "total_failures": 0,
            "unique_tests": 0,
            "top_error_types": [],
            "clusters": [],
        }

    # Count unique tests
    unique_tests = set(_make_test_key(f.classname, f.name) for f in failures)

    # Count error types
    error_types = defaultdict(int)
    for f in failures:
        if f.error_type:
            error_types[f.error_type] += 1

    top_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]

    # Get clusters
    clusters = cluster_failures(db, project, lookback_days)

    return {
        "project": project,
        "period_days": lookback_days,
        "total_failures": len(failures),
        "unique_tests": len(unique_tests),
        "top_error_types": [{"type": t, "count": c} for t, c in top_errors],
        "major_clusters": len([c for c in clusters if c["count"] >= 5]),
        "total_clusters": len(clusters),
    }
