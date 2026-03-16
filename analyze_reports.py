#!/usr/bin/env python3
"""
Analysis Demo Script.

This script demonstrates all analysis capabilities of the Test Report Analyzer:
- Flaky test detection
- Slow test detection
- Performance regressions
- Failure clustering
- Trend analysis

Run this after generating sample data with generate_sample_data.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from storage.database import SessionLocal
from analysis.flaky_detector import (
    detect_flaky_tests,
    get_flaky_test_summary,
    get_flaky_test_details,
)
from analysis.slow_detector import (
    detect_slow_tests,
    detect_performance_regressions,
    get_slowest_tests_by_total_time,
    get_duration_outliers,
    get_slow_test_summary,
)
from analysis.clustering import (
    cluster_failures,
    cluster_by_module,
    cluster_by_time,
    get_failure_summary,
)
from analysis.trends import (
    get_daily_trends,
    get_failure_rate_trend,
    get_duration_trend,
    get_test_growth_trend,
    detect_anomalies,
)


def print_section(title: str):
    """Print section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def demo_flaky_tests(db, project: str):
    """Demonstrate flaky test detection."""
    print_section("FLAKY TEST DETECTION")

    # Get summary
    summary = get_flaky_test_summary(db, project, lookback_runs=30)
    print(f"Project: {summary['project']}")
    print(f"Total flaky tests: {summary['total_flaky']}")
    print(f"  - Critical (>50%): {summary['critical_count']}")
    print(f"  - Moderate (30-50%): {summary['moderate_count']}")
    print(f"  - Mild (<30%): {summary['mild_count']}")
    print(f"Average flakiness: {summary['avg_flakiness']*100:.1f}%")

    if summary["most_flaky"]:
        print(f"\nMost flaky test: {summary['most_flaky']['test']}")
        print(f"  Flakiness score: {summary['most_flaky']['flakiness_score']*100:.1f}%")
        print(f"  Pattern: {summary['most_flaky']['recent_pattern']}")

    # Get detailed list
    print("\n--- Top Flaky Tests ---")
    flaky_tests = detect_flaky_tests(db, project, lookback_runs=30)

    for i, test in enumerate(flaky_tests[:5], 1):
        print(f"\n{i}. {test['test']}")
        print(
            f"   Flakiness: {test['flakiness_score']*100:.1f}% ({test['failures']}/{test['total_runs']} failures)"
        )
        print(f"   Recent pattern: {test['recent_pattern']}")
        print(f"   Transitions: {test['transitions']}")
        print(f"   Avg duration: {test['avg_duration']:.3f}s")


def demo_slow_tests(db, project: str):
    """Demonstrate slow test detection."""
    print_section("SLOW TEST DETECTION")

    # Get summary
    summary = get_slow_test_summary(db, project, threshold_seconds=5.0)
    print(f"Threshold: {summary['threshold']}s")
    print(f"Total slow tests: {summary['total_slow']}")
    print(f"Average duration: {summary['avg_slow_duration']:.2f}s")
    print(f"Total slow time: {summary['total_slow_time']:.2f}s")

    # Slow tests
    print("\n--- Slow Tests (>5s) ---")
    slow_tests = detect_slow_tests(db, project, threshold_seconds=5.0)

    for i, test in enumerate(slow_tests[:5], 1):
        print(f"\n{i}. {test['test']}")
        print(
            f"   Avg: {test['avg_duration']:.2f}s | Max: {test['max_duration']:.2f}s | Min: {test['min_duration']:.2f}s"
        )
        if "p50" in test:
            print(
                f"   Percentiles - P50: {test['p50']:.2f}s | P95: {test['p95']:.2f}s | P99: {test['p99']:.2f}s"
            )
        print(f"   Runs: {test['run_count']}")

    # Performance regressions
    print("\n--- Performance Regressions ---")
    regressions = detect_performance_regressions(
        db, project, lookback_days=7, comparison_days=30
    )

    if regressions:
        for i, reg in enumerate(regressions[:5], 1):
            print(f"\n{i}. {reg['test']}")
            print(
                f"   Baseline: {reg['baseline_avg']:.2f}s → Recent: {reg['recent_avg']:.2f}s"
            )
            print(
                f"   Increase: +{reg['increase_seconds']:.2f}s (+{reg['increase_percent']:.1f}%)"
            )
    else:
        print("No significant performance regressions detected.")

    # Total time consumers
    print("\n--- Biggest Time Consumers ---")
    time_consumers = get_slowest_tests_by_total_time(db, project, lookback_runs=30)

    for i, test in enumerate(time_consumers[:5], 1):
        print(f"\n{i}. {test['test']}")
        print(f"   Total time: {test['total_time']:.2f}s")
        print(f"   Avg per run: {test['avg_duration']:.2f}s × {test['run_count']} runs")

    # Duration outliers
    print("\n--- Duration Outliers (High Variance) ---")
    outliers = get_duration_outliers(db, project, min_runs=5)

    if outliers:
        for i, outlier in enumerate(outliers[:3], 1):
            print(f"\n{i}. {outlier['test']}")
            print(f"   Avg: {outlier['avg_duration']:.2f}s ± {outlier['stdev']:.2f}s")
            print(f"   Range: {outlier['min']:.2f}s - {outlier['max']:.2f}s")
            print(
                f"   Coefficient of Variation: {outlier['coefficient_of_variation']:.1f}%"
            )
    else:
        print("No significant outliers detected.")


def demo_failure_clustering(db, project: str):
    """Demonstrate failure clustering."""
    print_section("FAILURE CLUSTERING")

    # Summary
    summary = get_failure_summary(db, project, lookback_days=30)
    print(f"Period: Last {summary['period_days']} days")
    print(f"Total failures: {summary['total_failures']}")
    print(f"Unique tests affected: {summary['unique_tests']}")
    print(f"Total clusters: {summary['total_clusters']}")
    print(f"Major clusters (5+ failures): {summary['major_clusters']}")

    # Top error types
    print("\n--- Top Error Types ---")
    for i, error in enumerate(summary["top_error_types"][:5], 1):
        print(f"{i}. {error['type']}: {error['count']} occurrences")

    # Error pattern clusters
    print("\n--- Failure Clusters by Error Pattern ---")
    clusters = cluster_failures(db, project, lookback_days=30)

    for i, cluster in enumerate(clusters[:5], 1):
        print(f"\n{i}. {cluster['pattern']}")
        print(
            f"   Count: {cluster['count']} failures across {cluster['unique_tests']} unique tests"
        )
        print(f"   First: {cluster['first_occurrence']}")
        print(f"   Last: {cluster['last_occurrence']}")
        print(f"   Affected tests: {', '.join(cluster['affected_tests'][:3])}")
        if len(cluster["affected_tests"]) > 3:
            print(f"   ... and {len(cluster['affected_tests']) - 3} more")

    # Module clustering
    print("\n--- Failures by Module ---")
    modules = cluster_by_module(db, project, lookback_days=30)

    for i, module in enumerate(modules[:5], 1):
        print(f"\n{i}. {module['module']}")
        print(f"   Total failures: {module['total_failures']}")
        print(f"   Unique tests: {module['unique_tests']}")
        print(f"   Most common error: {module['most_common_error']}")

    # Temporal clustering
    print("\n--- Failure Spikes (Time Windows) ---")
    time_clusters = cluster_by_time(db, project, lookback_days=30, window_hours=24)
    spikes = [t for t in time_clusters if t.get("is_spike", False)]

    if spikes:
        for i, spike in enumerate(spikes[:5], 1):
            print(f"\n{i}. {spike['window_start']}")
            print(f"   Failure rate: {spike['failure_rate']:.1f}%")
            print(
                f"   Runs: {spike['test_runs']} | Tests: {spike['total_tests']} | Failures: {spike['total_failures']}"
            )
    else:
        print("No significant failure spikes detected.")


def demo_trends(db, project: str):
    """Demonstrate trend analysis."""
    print_section("TREND ANALYSIS")

    # Test growth trend
    print("--- Test Count Growth ---")
    growth = get_test_growth_trend(db, project, days=30)
    if growth["has_data"]:
        print(f"Trend: {growth['trend'].upper()}")
        print(f"First week avg: {growth['first_week_avg']:.0f} tests")
        print(f"Last week avg: {growth['last_week_avg']:.0f} tests")
        print(
            f"Change: {growth['change']:+.0f} tests ({growth['change_percent']:+.1f}%)"
        )

    # Failure rate trend
    print("\n--- Failure Rate Trend ---")
    failure_trend = get_failure_rate_trend(db, project, days=30)
    if failure_trend["has_data"]:
        print(f"Trend: {failure_trend['trend'].upper()}")
        print(f"First week avg: {failure_trend['first_week_avg']:.2f}%")
        print(f"Last week avg: {failure_trend['last_week_avg']:.2f}%")
        print(f"Overall avg: {failure_trend['overall_avg']:.2f}%")
        print(f"Change: {failure_trend['change']:+.2f}%")
        print(
            f"Range: {failure_trend['min_rate']:.2f}% - {failure_trend['max_rate']:.2f}%"
        )

    # Duration trend
    print("\n--- Test Duration Trend ---")
    duration_trend = get_duration_trend(db, project, days=30)
    if duration_trend["has_data"]:
        print(f"Trend: {duration_trend['trend'].upper()}")
        print(f"First week avg: {duration_trend['first_week_avg']:.2f}s")
        print(f"Last week avg: {duration_trend['last_week_avg']:.2f}s")
        print(
            f"Change: {duration_trend['change']:+.2f}s ({duration_trend['change_percent']:+.1f}%)"
        )

    # Anomalies
    print("\n--- Detected Anomalies ---")
    anomalies = detect_anomalies(db, project, days=30)

    if anomalies:
        for i, anomaly in enumerate(anomalies[:5], 1):
            print(f"\n{i}. {anomaly['date']}")
            for reason in anomaly["anomalies"]:
                print(
                    f"   {reason['metric']}: {reason['value']} (avg: {reason['avg']}, z-score: {reason['z_score']})"
                )
    else:
        print("No significant anomalies detected.")

    # Daily trends (last 7 days)
    print("\n--- Recent Daily Trends ---")
    daily = get_daily_trends(db, project, days=7)

    if daily:
        print(
            f"{'Date':<12} {'Runs':<6} {'Tests':<7} {'Pass%':<7} {'Fail%':<7} {'Duration':<10}"
        )
        print("-" * 60)
        for day in daily:
            print(
                f"{day['date']:<12} {day['runs']:<6} {day['total_tests']:<7} "
                f"{day['pass_rate']:<7.1f} {day['failure_rate']:<7.1f} {day['avg_duration']:<10.2f}s"
            )


def main():
    """Run all analysis demos."""
    print("\n" + "=" * 70)
    print("  TEST REPORT ANALYZER - ANALYSIS DEMONSTRATION")
    print("=" * 70)

    db = SessionLocal()
    project = "demo"

    try:
        # Check if we have data
        from storage.models import TestRun

        run_count = db.query(TestRun).filter(TestRun.project == project).count()

        if run_count == 0:
            print("\n⚠️  No test data found in database!")
            print(
                "Please run 'python generate_sample_data.py' first to create sample data.\n"
            )
            return

        print(f"\nAnalyzing project: {project}")
        print(f"Test runs in database: {run_count}\n")

        # Run all demos
        demo_flaky_tests(db, project)
        demo_slow_tests(db, project)
        demo_failure_clustering(db, project)
        demo_trends(db, project)

        print("\n" + "=" * 70)
        print("  ANALYSIS COMPLETE")
        print("=" * 70 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    main()
