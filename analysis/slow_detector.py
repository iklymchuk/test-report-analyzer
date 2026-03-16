"""
Slow Test Detection Module.

This module identifies tests that exceed performance thresholds and provides
insights into test duration patterns, outliers, and performance regressions.

Metrics tracked:
- Average duration per test
- Percentiles (P50, P95, P99)
- Maximum duration
- Duration trends over time
- Outlier detection
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import statistics

from storage.models import TestRun, TestCase


def detect_slow_tests(
    db: Session,
    project: str,
    threshold_seconds: float = 5.0,
    min_runs: int = 1,
    include_percentiles: bool = True,
) -> List[Dict]:
    """
    Identify tests exceeding performance thresholds.

    Args:
        db: Database session
        project: Project name to analyze
        threshold_seconds: Duration threshold in seconds
        min_runs: Minimum number of runs to consider a test
        include_percentiles: Calculate P50, P95, P99 percentiles

    Returns:
        List of slow test dictionaries with performance metrics

    Example:
        ```python
        db = SessionLocal()
        slow_tests = detect_slow_tests(db, "my-app", threshold_seconds=10.0)

        for test in slow_tests:
            print(f"{test['test']}: avg {test['avg_duration']:.2f}s")
        ```
    """
    # Query to get aggregated test durations
    query = (
        db.query(
            TestCase.classname,
            TestCase.name,
            func.avg(TestCase.duration_seconds).label("avg_duration"),
            func.max(TestCase.duration_seconds).label("max_duration"),
            func.min(TestCase.duration_seconds).label("min_duration"),
            func.count(TestCase.id).label("run_count"),
        )
        .join(TestRun)
        .filter(TestRun.project == project, TestCase.duration_seconds.isnot(None))
        .group_by(TestCase.classname, TestCase.name)
        .having(
            func.avg(TestCase.duration_seconds) > threshold_seconds,
            func.count(TestCase.id) >= min_runs,
        )
        .order_by(desc("avg_duration"))
    )

    results = query.all()

    slow_tests = []

    for row in results:
        test_key = _make_test_key(row.classname, row.name)

        test_data = {
            "test": test_key,
            "classname": row.classname or "",
            "name": row.name,
            "avg_duration": round(row.avg_duration, 3),
            "max_duration": round(row.max_duration, 3),
            "min_duration": round(row.min_duration, 3),
            "run_count": row.run_count,
            "threshold_exceeded_by": round(row.avg_duration - threshold_seconds, 3),
        }

        # Calculate percentiles if requested
        if include_percentiles:
            percentiles = _calculate_percentiles(db, project, row.classname, row.name)
            test_data.update(percentiles)

        slow_tests.append(test_data)

    return slow_tests


def detect_performance_regressions(
    db: Session,
    project: str,
    lookback_days: int = 7,
    comparison_days: int = 30,
    threshold_increase: float = 0.20,
) -> List[Dict]:
    """
    Detect tests with performance regressions.

    Compares recent performance (last N days) against a baseline period
    to identify tests that have gotten significantly slower.

    Args:
        db: Database session
        project: Project name
        lookback_days: Recent period to analyze (default: 7 days)
        comparison_days: Historical baseline period (default: 30 days)
        threshold_increase: Minimum increase to flag (0.20 = 20%)

    Returns:
        List of tests with performance regressions

    Example:
        ```python
        regressions = detect_performance_regressions(db, "my-app")
        for test in regressions:
            print(f"{test['test']}: {test['increase_percent']:.1f}% slower")
        ```
    """
    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=lookback_days)
    baseline_cutoff = now - timedelta(days=comparison_days)

    # Get all test cases in the time period
    test_cases = (
        db.query(TestCase, TestRun)
        .join(TestRun)
        .filter(
            TestRun.project == project,
            TestRun.timestamp >= baseline_cutoff,
            TestCase.duration_seconds.isnot(None),
        )
        .all()
    )

    # Group by test and split into recent vs baseline
    from collections import defaultdict

    test_durations = defaultdict(lambda: {"recent": [], "baseline": []})

    for case, run in test_cases:
        test_key = _make_test_key(case.classname, case.name)

        if run.timestamp >= recent_cutoff:
            test_durations[test_key]["recent"].append(case.duration_seconds)
        else:
            test_durations[test_key]["baseline"].append(case.duration_seconds)

    # Calculate regressions
    regressions = []

    for test_key, durations in test_durations.items():
        recent = durations["recent"]
        baseline = durations["baseline"]

        # Need data from both periods
        if not recent or not baseline:
            continue

        # Need minimum runs
        if len(recent) < 2 or len(baseline) < 2:
            continue

        recent_avg = statistics.mean(recent)
        baseline_avg = statistics.mean(baseline)

        # Calculate increase
        if baseline_avg == 0:
            continue

        increase = (recent_avg - baseline_avg) / baseline_avg

        if increase >= threshold_increase:
            regressions.append(
                {
                    "test": test_key,
                    "baseline_avg": round(baseline_avg, 3),
                    "recent_avg": round(recent_avg, 3),
                    "increase_seconds": round(recent_avg - baseline_avg, 3),
                    "increase_percent": round(increase * 100, 1),
                    "baseline_runs": len(baseline),
                    "recent_runs": len(recent),
                }
            )

    return sorted(regressions, key=lambda x: x["increase_percent"], reverse=True)


def get_test_duration_history(
    db: Session, test_name: str, project: str, lookback_runs: int = 50
) -> Optional[Dict]:
    """
    Get duration history for a specific test.

    Args:
        db: Database session
        test_name: Full test identifier (classname::name)
        project: Project name
        lookback_runs: Number of recent runs

    Returns:
        Dictionary with duration statistics and history
    """
    # Parse test name
    if "::" in test_name:
        classname, name = test_name.split("::", 1)
    else:
        classname = None
        name = test_name

    # Get recent test runs
    query = (
        db.query(TestCase, TestRun)
        .join(TestRun)
        .filter(
            TestRun.project == project,
            TestCase.name == name,
            TestCase.duration_seconds.isnot(None),
        )
    )

    if classname:
        query = query.filter(TestCase.classname == classname)

    results = query.order_by(desc(TestRun.timestamp)).limit(lookback_runs).all()

    if not results:
        return None

    durations = [case.duration_seconds for case, _ in results]
    timestamps = [run.timestamp.isoformat() for _, run in results]

    return {
        "test": test_name,
        "project": project,
        "run_count": len(durations),
        "avg_duration": round(statistics.mean(durations), 3),
        "min_duration": round(min(durations), 3),
        "max_duration": round(max(durations), 3),
        "median_duration": round(statistics.median(durations), 3),
        "stdev": round(statistics.stdev(durations), 3) if len(durations) > 1 else 0,
        "duration_history": [
            round(d, 3) for d in reversed(durations)
        ],  # Chronological order
        "timestamp_history": list(reversed(timestamps)),
    }


def get_slowest_tests_by_total_time(
    db: Session, project: str, lookback_runs: int = 20, limit: int = 20
) -> List[Dict]:
    """
    Identify tests consuming the most total CI time.

    This helps prioritize optimization efforts by finding tests that,
    even if not individually slow, add up to significant time due to
    being run frequently.

    Args:
        db: Database session
        project: Project name
        lookback_runs: Number of recent runs to analyze
        limit: Maximum number of tests to return

    Returns:
        List of tests sorted by total time consumed
    """
    # Get recent test runs
    recent_runs = (
        db.query(TestRun)
        .filter(TestRun.project == project)
        .order_by(desc(TestRun.timestamp))
        .limit(lookback_runs)
        .all()
    )

    if not recent_runs:
        return []

    run_ids = [run.id for run in recent_runs]

    # Aggregate total time per test
    query = (
        db.query(
            TestCase.classname,
            TestCase.name,
            func.sum(TestCase.duration_seconds).label("total_time"),
            func.avg(TestCase.duration_seconds).label("avg_duration"),
            func.count(TestCase.id).label("run_count"),
        )
        .filter(
            TestCase.test_run_id.in_(run_ids), TestCase.duration_seconds.isnot(None)
        )
        .group_by(TestCase.classname, TestCase.name)
        .order_by(desc("total_time"))
        .limit(limit)
    )

    results = query.all()

    return [
        {
            "test": _make_test_key(row.classname, row.name),
            "total_time": round(row.total_time, 3),
            "avg_duration": round(row.avg_duration, 3),
            "run_count": row.run_count,
            "time_per_run": round(row.total_time / lookback_runs, 3),
        }
        for row in results
    ]


def get_duration_outliers(
    db: Session, project: str, min_runs: int = 5, std_threshold: float = 3.0
) -> List[Dict]:
    """
    Detect tests with inconsistent durations (high variance).

    Uses standard deviation to find tests whose execution time varies
    significantly, which may indicate environmental issues or flakiness.

    Args:
        db: Database session
        project: Project name
        min_runs: Minimum runs required to calculate variance
        std_threshold: Number of standard deviations for outlier detection

    Returns:
        List of tests with high duration variance
    """
    # Get all tests with sufficient runs
    query = (
        db.query(TestCase.classname, TestCase.name)
        .join(TestRun)
        .filter(TestRun.project == project, TestCase.duration_seconds.isnot(None))
        .group_by(TestCase.classname, TestCase.name)
        .having(func.count(TestCase.id) >= min_runs)
    )

    results = query.all()

    outliers = []

    for row in results:
        # Get all durations for this test
        durations_query = (
            db.query(TestCase.duration_seconds)
            .join(TestRun)
            .filter(
                TestRun.project == project,
                TestCase.classname == row.classname,
                TestCase.name == row.name,
                TestCase.duration_seconds.isnot(None),
            )
        )

        durations = [d[0] for d in durations_query.all()]

        if len(durations) < min_runs:
            continue

        avg = statistics.mean(durations)
        stdev = statistics.stdev(durations) if len(durations) > 1 else 0

        # Calculate coefficient of variation (CV)
        cv = (stdev / avg * 100) if avg > 0 else 0

        # Flag if variance is high
        if cv > 50:  # 50% coefficient of variation
            test_key = _make_test_key(row.classname, row.name)
            outliers.append(
                {
                    "test": test_key,
                    "avg_duration": round(avg, 3),
                    "stdev": round(stdev, 3),
                    "min": round(min(durations), 3),
                    "max": round(max(durations), 3),
                    "coefficient_of_variation": round(cv, 1),
                    "run_count": len(durations),
                }
            )

    return sorted(outliers, key=lambda x: x["coefficient_of_variation"], reverse=True)


def _calculate_percentiles(
    db: Session, project: str, classname: Optional[str], name: str
) -> Dict:
    """Calculate P50, P95, P99 percentiles for a test."""
    # Get all durations
    query = (
        db.query(TestCase.duration_seconds)
        .join(TestRun)
        .filter(
            TestRun.project == project,
            TestCase.name == name,
            TestCase.duration_seconds.isnot(None),
        )
    )

    if classname:
        query = query.filter(TestCase.classname == classname)

    durations = [d[0] for d in query.all()]

    if not durations:
        return {"p50": 0, "p95": 0, "p99": 0}

    # Sort durations
    sorted_durations = sorted(durations)

    def percentile(data, p):
        """Calculate percentile."""
        k = (len(data) - 1) * p / 100
        f = int(k)
        c = f + 1
        if c >= len(data):
            return data[-1]
        d0 = data[f]
        d1 = data[c]
        return d0 + (d1 - d0) * (k - f)

    return {
        "p50": round(percentile(sorted_durations, 50), 3),
        "p95": round(percentile(sorted_durations, 95), 3),
        "p99": round(percentile(sorted_durations, 99), 3),
    }


def _make_test_key(classname: Optional[str], name: str) -> str:
    """Create unique test identifier."""
    if classname:
        return f"{classname}::{name}"
    return name


def get_slow_test_summary(
    db: Session, project: str, threshold_seconds: float = 5.0
) -> Dict:
    """
    Get high-level summary of slow test situation.

    Args:
        db: Database session
        project: Project name
        threshold_seconds: Duration threshold

    Returns:
        Summary statistics
    """
    slow_tests = detect_slow_tests(
        db, project, threshold_seconds, include_percentiles=False
    )

    if not slow_tests:
        return {
            "project": project,
            "threshold": threshold_seconds,
            "total_slow": 0,
            "avg_slow_duration": 0,
            "slowest_test": None,
            "total_slow_time": 0,
        }

    total_time = sum(t["avg_duration"] * t["run_count"] for t in slow_tests)
    avg_duration = sum(t["avg_duration"] for t in slow_tests) / len(slow_tests)

    return {
        "project": project,
        "threshold": threshold_seconds,
        "total_slow": len(slow_tests),
        "avg_slow_duration": round(avg_duration, 3),
        "slowest_test": slow_tests[0] if slow_tests else None,
        "total_slow_time": round(total_time, 3),
    }
