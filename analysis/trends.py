"""
Trend Analysis Module.

This module provides time-series analysis of test metrics to identify
patterns, anomalies, and long-term trends in test health.

Metrics tracked over time:
- Daily/weekly failure rates
- Test count growth
- Average duration trends
- Pass rate trends
- Flaky test trends
"""

from typing import List, Dict
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
from sqlalchemy.orm import Session

from storage.models import TestRun


def get_daily_trends(db: Session, project: str, days: int = 30) -> List[Dict]:
    """
    Get daily aggregated metrics for a project.

    Args:
        db: Database session
        project: Project name
        days: Number of days to look back

    Returns:
        List of daily metrics sorted chronologically

    Example:
        ```python
        trends = get_daily_trends(db, "my-app", days=14)
        for day in trends:
            print(f"{day['date']}: {day['failure_rate']:.1f}% failures")
        ```
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Get all test runs in the period
    runs = (
        db.query(TestRun)
        .filter(TestRun.project == project, TestRun.timestamp >= cutoff)
        .order_by(TestRun.timestamp)
        .all()
    )

    if not runs:
        return []

    # Group by date
    daily_data = defaultdict(list)

    for run in runs:
        day = run.timestamp.date()
        daily_data[day].append(run)

    # Calculate daily metrics
    result = []

    for day in sorted(daily_data.keys()):
        day_runs = daily_data[day]

        total_tests = sum(r.total_tests for r in day_runs if r.total_tests)
        total_passed = sum(r.passed for r in day_runs if r.passed)
        total_failed = sum(r.failed for r in day_runs if r.failed)
        total_skipped = sum(r.skipped for r in day_runs if r.skipped)

        durations = [r.duration_seconds for r in day_runs if r.duration_seconds]
        avg_duration = statistics.mean(durations) if durations else 0

        failure_rate = (total_failed / total_tests * 100) if total_tests > 0 else 0
        pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

        result.append(
            {
                "date": day.isoformat(),
                "runs": len(day_runs),
                "total_tests": total_tests,
                "passed": total_passed,
                "failed": total_failed,
                "skipped": total_skipped,
                "failure_rate": round(failure_rate, 2),
                "pass_rate": round(pass_rate, 2),
                "avg_duration": round(avg_duration, 2),
            }
        )

    return result


def get_weekly_trends(db: Session, project: str, weeks: int = 12) -> List[Dict]:
    """
    Get weekly aggregated metrics.

    Args:
        db: Database session
        project: Project name
        weeks: Number of weeks to look back

    Returns:
        List of weekly metrics
    """
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)

    runs = (
        db.query(TestRun)
        .filter(TestRun.project == project, TestRun.timestamp >= cutoff)
        .order_by(TestRun.timestamp)
        .all()
    )

    if not runs:
        return []

    # Group by week (ISO week)
    weekly_data = defaultdict(list)

    for run in runs:
        # Get ISO week number
        iso_year, iso_week, _ = run.timestamp.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        weekly_data[week_key].append(run)

    # Calculate weekly metrics
    result = []

    for week in sorted(weekly_data.keys()):
        week_runs = weekly_data[week]

        total_tests = sum(r.total_tests for r in week_runs if r.total_tests)
        total_failed = sum(r.failed for r in week_runs if r.failed)
        total_passed = sum(r.passed for r in week_runs if r.passed)

        durations = [r.duration_seconds for r in week_runs if r.duration_seconds]
        avg_duration = statistics.mean(durations) if durations else 0

        failure_rate = (total_failed / total_tests * 100) if total_tests > 0 else 0

        result.append(
            {
                "week": week,
                "runs": len(week_runs),
                "total_tests": total_tests,
                "passed": total_passed,
                "failed": total_failed,
                "failure_rate": round(failure_rate, 2),
                "avg_duration": round(avg_duration, 2),
            }
        )

    return result


def detect_anomalies(
    db: Session, project: str, days: int = 30, std_threshold: float = 2.0
) -> List[Dict]:
    """
    Detect anomalous days based on statistical analysis.

    Uses standard deviation to identify days with unusually high
    failure rates or test counts.

    Args:
        db: Database session
        project: Project name
        days: Number of days to analyze
        std_threshold: Number of standard deviations for anomaly detection

    Returns:
        List of anomalous days
    """
    trends = get_daily_trends(db, project, days)

    if len(trends) < 7:  # Need minimum data
        return []

    # Calculate baseline statistics
    failure_rates = [d["failure_rate"] for d in trends]
    test_counts = [d["total_tests"] for d in trends]

    avg_failure_rate = statistics.mean(failure_rates)
    std_failure_rate = statistics.stdev(failure_rates) if len(failure_rates) > 1 else 0

    avg_test_count = statistics.mean(test_counts)
    std_test_count = statistics.stdev(test_counts) if len(test_counts) > 1 else 0

    # Detect anomalies
    anomalies = []

    for day_data in trends:
        anomaly_reasons = []

        # Check failure rate anomaly
        if std_failure_rate > 0:
            z_score = (day_data["failure_rate"] - avg_failure_rate) / std_failure_rate
            if abs(z_score) > std_threshold:
                anomaly_reasons.append(
                    {
                        "metric": "failure_rate",
                        "value": day_data["failure_rate"],
                        "avg": round(avg_failure_rate, 2),
                        "z_score": round(z_score, 2),
                    }
                )

        # Check test count anomaly
        if std_test_count > 0:
            z_score = (day_data["total_tests"] - avg_test_count) / std_test_count
            if abs(z_score) > std_threshold:
                anomaly_reasons.append(
                    {
                        "metric": "test_count",
                        "value": day_data["total_tests"],
                        "avg": round(avg_test_count, 0),
                        "z_score": round(z_score, 2),
                    }
                )

        if anomaly_reasons:
            anomalies.append(
                {
                    "date": day_data["date"],
                    "anomalies": anomaly_reasons,
                    "data": day_data,
                }
            )

    return sorted(anomalies, key=lambda x: x["date"], reverse=True)


def calculate_moving_average(
    db: Session, project: str, days: int = 30, window: int = 7
) -> List[Dict]:
    """
    Calculate moving average for smoothing trends.

    Args:
        db: Database session
        project: Project name
        days: Total period to analyze
        window: Size of moving average window

    Returns:
        List of dates with moving averages
    """
    trends = get_daily_trends(db, project, days)

    if len(trends) < window:
        return []

    result = []

    for i in range(window - 1, len(trends)):
        window_data = trends[i - window + 1 : i + 1]

        avg_failure_rate = statistics.mean([d["failure_rate"] for d in window_data])
        avg_duration = statistics.mean([d["avg_duration"] for d in window_data])
        avg_tests = statistics.mean([d["total_tests"] for d in window_data])

        result.append(
            {
                "date": trends[i]["date"],
                "ma_failure_rate": round(avg_failure_rate, 2),
                "ma_duration": round(avg_duration, 2),
                "ma_test_count": round(avg_tests, 0),
            }
        )

    return result


def get_test_growth_trend(db: Session, project: str, days: int = 90) -> Dict:
    """
    Analyze test count growth over time.

    Args:
        db: Database session
        project: Project name
        days: Period to analyze

    Returns:
        Growth statistics and trend direction
    """
    trends = get_daily_trends(db, project, days)

    if len(trends) < 7:
        return {"project": project, "period_days": days, "has_data": False}

    # Get first and last week averages
    first_week = trends[:7]
    last_week = trends[-7:]

    first_avg = statistics.mean([d["total_tests"] for d in first_week])
    last_avg = statistics.mean([d["total_tests"] for d in last_week])

    change = last_avg - first_avg
    change_percent = (change / first_avg * 100) if first_avg > 0 else 0

    # Determine trend direction
    if abs(change_percent) < 5:
        trend = "stable"
    elif change_percent > 0:
        trend = "growing"
    else:
        trend = "declining"

    return {
        "project": project,
        "period_days": days,
        "has_data": True,
        "first_week_avg": round(first_avg, 0),
        "last_week_avg": round(last_avg, 0),
        "change": round(change, 0),
        "change_percent": round(change_percent, 1),
        "trend": trend,
    }


def get_failure_rate_trend(db: Session, project: str, days: int = 30) -> Dict:
    """
    Analyze failure rate trend.

    Args:
        db: Database session
        project: Project name
        days: Period to analyze

    Returns:
        Failure rate trend analysis
    """
    trends = get_daily_trends(db, project, days)

    if len(trends) < 7:
        return {"project": project, "has_data": False}

    failure_rates = [d["failure_rate"] for d in trends]

    first_week = failure_rates[:7]
    last_week = failure_rates[-7:]

    first_avg = statistics.mean(first_week)
    last_avg = statistics.mean(last_week)
    overall_avg = statistics.mean(failure_rates)

    change = last_avg - first_avg

    # Determine trend
    if abs(change) < 2:  # Less than 2% change
        trend = "stable"
    elif change > 0:
        trend = "worsening"
    else:
        trend = "improving"

    return {
        "project": project,
        "period_days": days,
        "has_data": True,
        "first_week_avg": round(first_avg, 2),
        "last_week_avg": round(last_avg, 2),
        "overall_avg": round(overall_avg, 2),
        "change": round(change, 2),
        "trend": trend,
        "min_rate": round(min(failure_rates), 2),
        "max_rate": round(max(failure_rates), 2),
    }


def get_duration_trend(db: Session, project: str, days: int = 30) -> Dict:
    """
    Analyze test duration trend.

    Args:
        db: Database session
        project: Project name
        days: Period to analyze

    Returns:
        Duration trend analysis
    """
    trends = get_daily_trends(db, project, days)

    if len(trends) < 7:
        return {"project": project, "has_data": False}

    durations = [d["avg_duration"] for d in trends if d["avg_duration"] > 0]

    if not durations:
        return {"project": project, "has_data": False}

    first_week = durations[:7]
    last_week = durations[-7:]

    first_avg = statistics.mean(first_week)
    last_avg = statistics.mean(last_week)
    overall_avg = statistics.mean(durations)

    change = last_avg - first_avg
    change_percent = (change / first_avg * 100) if first_avg > 0 else 0

    # Determine trend
    if abs(change_percent) < 10:  # Less than 10% change
        trend = "stable"
    elif change_percent > 0:
        trend = "slowing"
    else:
        trend = "improving"

    return {
        "project": project,
        "period_days": days,
        "has_data": True,
        "first_week_avg": round(first_avg, 2),
        "last_week_avg": round(last_avg, 2),
        "overall_avg": round(overall_avg, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 1),
        "trend": trend,
    }


def compare_time_periods(
    db: Session,
    project: str,
    period1_days: int = 7,
    period2_days: int = 7,
    gap_days: int = 0,
) -> Dict:
    """
    Compare metrics between two time periods.

    Useful for A/B testing, before/after analysis, etc.

    Args:
        db: Database session
        project: Project name
        period1_days: Length of recent period
        period2_days: Length of comparison period
        gap_days: Gap between periods

    Returns:
        Comparison statistics

    Example:
        # Compare last week vs previous week
        comparison = compare_time_periods(db, "my-app", 7, 7, 0)
    """
    now = datetime.utcnow()

    # Define periods
    period1_start = now - timedelta(days=period1_days)
    period1_end = now

    period2_end = period1_start - timedelta(days=gap_days)
    period2_start = period2_end - timedelta(days=period2_days)

    # Get runs for each period
    period1_runs = (
        db.query(TestRun)
        .filter(
            TestRun.project == project,
            TestRun.timestamp >= period1_start,
            TestRun.timestamp <= period1_end,
        )
        .all()
    )

    period2_runs = (
        db.query(TestRun)
        .filter(
            TestRun.project == project,
            TestRun.timestamp >= period2_start,
            TestRun.timestamp <= period2_end,
        )
        .all()
    )

    def calculate_metrics(runs):
        if not runs:
            return None

        total_tests = sum(r.total_tests for r in runs if r.total_tests)
        total_failed = sum(r.failed for r in runs if r.failed)
        durations = [r.duration_seconds for r in runs if r.duration_seconds]

        return {
            "runs": len(runs),
            "total_tests": total_tests,
            "total_failed": total_failed,
            "failure_rate": round(
                (total_failed / total_tests * 100) if total_tests > 0 else 0, 2
            ),
            "avg_duration": round(statistics.mean(durations), 2) if durations else 0,
        }

    period1_metrics = calculate_metrics(period1_runs)
    period2_metrics = calculate_metrics(period2_runs)

    if not period1_metrics or not period2_metrics:
        return {"project": project, "has_data": False}

    # Calculate changes
    failure_rate_change = (
        period1_metrics["failure_rate"] - period2_metrics["failure_rate"]
    )
    duration_change = period1_metrics["avg_duration"] - period2_metrics["avg_duration"]

    return {
        "project": project,
        "has_data": True,
        "period1": {
            "start": period1_start.isoformat(),
            "end": period1_end.isoformat(),
            "metrics": period1_metrics,
        },
        "period2": {
            "start": period2_start.isoformat(),
            "end": period2_end.isoformat(),
            "metrics": period2_metrics,
        },
        "changes": {
            "failure_rate": round(failure_rate_change, 2),
            "avg_duration": round(duration_change, 2),
        },
    }


def get_comprehensive_summary(db: Session, project: str, days: int = 30) -> Dict:
    """
    Get comprehensive trend summary for a project.

    Args:
        db: Database session
        project: Project name
        days: Period to analyze

    Returns:
        Complete trend analysis summary
    """
    return {
        "project": project,
        "period_days": days,
        "test_growth": get_test_growth_trend(db, project, days),
        "failure_rate": get_failure_rate_trend(db, project, days),
        "duration": get_duration_trend(db, project, days),
        "anomalies": detect_anomalies(db, project, days),
        "daily_data": get_daily_trends(db, project, days),
    }
