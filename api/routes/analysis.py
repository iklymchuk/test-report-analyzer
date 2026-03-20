"""
Analysis API Routes.

Endpoints for test analysis including flaky tests, slow tests, and failure clustering.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
import logging

from storage.database import SessionLocal
from storage.models import TestCase, TestRun
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
    get_test_duration_history,
)
from analysis.clustering import (
    cluster_failures,
    cluster_by_module,
    cluster_by_time,
    find_related_failures,
    get_failure_summary,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/tests/flaky")
async def get_flaky_tests(
    project: str = Query(..., description="Project name"),
    lookback_runs: int = Query(
        20, ge=1, le=100, description="Number of recent runs to analyze"
    ),
    min_flakiness: float = Query(
        0.1, ge=0.0, le=1.0, description="Minimum flakiness score"
    ),
    max_flakiness: float = Query(
        0.9, ge=0.0, le=1.0, description="Maximum flakiness score"
    ),
    db: Session = Depends(get_db),
):
    """
    Get flaky tests for a project.

    Identifies tests with inconsistent pass/fail patterns across multiple runs.

    **Parameters:**
    - **project**: Project name to analyze
    - **lookback_runs**: Number of recent test runs to examine (1-100)
    - **min_flakiness**: Minimum flakiness score threshold (0.0-1.0)
    - **max_flakiness**: Maximum flakiness score threshold (0.0-1.0)

    **Returns:**
    - List of flaky tests with metrics and patterns
    """
    try:
        flaky_tests = detect_flaky_tests(
            db,
            project,
            lookback_runs=lookback_runs,
            min_flakiness=min_flakiness,
            max_flakiness=max_flakiness,
        )

        summary = get_flaky_test_summary(db, project, lookback_runs)

        return {
            "project": project,
            "lookback_runs": lookback_runs,
            "summary": summary,
            "flaky_tests": flaky_tests,
        }
    except Exception as e:
        logger.error(f"Error detecting flaky tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/flaky/{test_name:path}")
async def get_flaky_test_detail(
    test_name: str,
    project: str = Query(..., description="Project name"),
    lookback_runs: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific flaky test.

    **Parameters:**
    - **test_name**: Full test identifier (e.g., "tests.api::test_login")
    - **project**: Project name
    - **lookback_runs**: Number of recent runs to examine

    **Returns:**
    - Detailed test history and statistics
    """
    try:
        details = get_flaky_test_details(db, test_name, project, lookback_runs)

        if not details:
            raise HTTPException(
                status_code=404,
                detail=f"Test '{test_name}' not found in project '{project}'",
            )

        return details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting flaky test details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/slow")
async def get_slow_tests(
    project: str = Query(..., description="Project name"),
    threshold_seconds: float = Query(
        5.0, ge=0.1, description="Duration threshold in seconds"
    ),
    min_runs: int = Query(1, ge=1, description="Minimum number of runs"),
    include_percentiles: bool = Query(
        True, description="Include P50/P95/P99 percentiles"
    ),
    db: Session = Depends(get_db),
):
    """
    Get slow tests exceeding duration threshold.

    **Parameters:**
    - **project**: Project name to analyze
    - **threshold_seconds**: Minimum duration to be considered slow
    - **min_runs**: Minimum number of runs required
    - **include_percentiles**: Calculate percentiles (may be slower)

    **Returns:**
    - List of slow tests with performance metrics
    """
    try:
        slow_tests = detect_slow_tests(
            db,
            project,
            threshold_seconds=threshold_seconds,
            min_runs=min_runs,
            include_percentiles=include_percentiles,
        )

        summary = get_slow_test_summary(db, project, threshold_seconds)

        return {
            "project": project,
            "threshold_seconds": threshold_seconds,
            "summary": summary,
            "slow_tests": slow_tests,
        }
    except Exception as e:
        logger.error(f"Error detecting slow tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/slow/regressions")
async def get_performance_regressions(
    project: str = Query(..., description="Project name"),
    lookback_days: int = Query(7, ge=1, le=90, description="Recent period in days"),
    comparison_days: int = Query(
        30, ge=1, le=365, description="Baseline period in days"
    ),
    threshold_increase: float = Query(
        0.20, ge=0.0, le=10.0, description="Minimum increase (e.g., 0.20 = 20%)"
    ),
    db: Session = Depends(get_db),
):
    """
    Detect performance regressions.

    Compares recent test performance against historical baseline.

    **Parameters:**
    - **project**: Project name
    - **lookback_days**: Recent period to analyze
    - **comparison_days**: Historical baseline period
    - **threshold_increase**: Minimum % increase to flag (0.20 = 20%)

    **Returns:**
    - List of tests with performance regressions
    """
    try:
        regressions = detect_performance_regressions(
            db,
            project,
            lookback_days=lookback_days,
            comparison_days=comparison_days,
            threshold_increase=threshold_increase,
        )

        return {
            "project": project,
            "lookback_days": lookback_days,
            "comparison_days": comparison_days,
            "threshold_increase": threshold_increase,
            "regressions": regressions,
        }
    except Exception as e:
        logger.error(f"Error detecting regressions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/slow/total-time")
async def get_time_consumers(
    project: str = Query(..., description="Project name"),
    lookback_runs: int = Query(20, ge=1, le=100),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Get tests consuming the most total CI time.

    **Parameters:**
    - **project**: Project name
    - **lookback_runs**: Number of recent runs
    - **limit**: Maximum tests to return

    **Returns:**
    - Tests sorted by total time consumed
    """
    try:
        time_consumers = get_slowest_tests_by_total_time(
            db, project, lookback_runs=lookback_runs, limit=limit
        )

        return {
            "project": project,
            "lookback_runs": lookback_runs,
            "time_consumers": time_consumers,
        }
    except Exception as e:
        logger.error(f"Error getting time consumers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/slow/outliers")
async def get_duration_variance(
    project: str = Query(..., description="Project name"),
    min_runs: int = Query(5, ge=2),
    db: Session = Depends(get_db),
):
    """
    Get tests with inconsistent durations (high variance).

    **Parameters:**
    - **project**: Project name
    - **min_runs**: Minimum runs required

    **Returns:**
    - Tests with high duration variance
    """
    try:
        outliers = get_duration_outliers(db, project, min_runs=min_runs)

        return {"project": project, "min_runs": min_runs, "outliers": outliers}
    except Exception as e:
        logger.error(f"Error getting outliers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/{test_name:path}/duration-history")
async def get_duration_history(
    test_name: str,
    project: str = Query(..., description="Project name"),
    lookback_runs: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get duration history for a specific test.

    **Parameters:**
    - **test_name**: Full test identifier
    - **project**: Project name
    - **lookback_runs**: Number of recent runs

    **Returns:**
    - Duration statistics and history
    """
    try:
        history = get_test_duration_history(db, test_name, project, lookback_runs)

        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"Test '{test_name}' not found in project '{project}'",
            )

        return history
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting duration history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/failures/clusters")
async def get_failure_clusters(
    project: str = Query(..., description="Project name"),
    lookback_days: int = Query(7, ge=1, le=90, description="Days to look back"),
    min_cluster_size: int = Query(2, ge=2, description="Minimum failures per cluster"),
    db: Session = Depends(get_db),
):
    """
    Get failure clusters grouped by error pattern.

    **Parameters:**
    - **project**: Project name
    - **lookback_days**: Days to analyze
    - **min_cluster_size**: Minimum failures to form a cluster

    **Returns:**
    - Failure clusters with patterns and affected tests
    """
    try:
        clusters = cluster_failures(
            db, project, lookback_days=lookback_days, min_cluster_size=min_cluster_size
        )

        summary = get_failure_summary(db, project, lookback_days)

        return {
            "project": project,
            "lookback_days": lookback_days,
            "summary": summary,
            "clusters": clusters,
        }
    except Exception as e:
        logger.error(f"Error clustering failures: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/failures/by-module")
async def get_failures_by_module(
    project: str = Query(..., description="Project name"),
    lookback_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """
    Get failures grouped by module/package.

    **Parameters:**
    - **project**: Project name
    - **lookback_days**: Days to analyze

    **Returns:**
    - Failures grouped by code module
    """
    try:
        modules = cluster_by_module(db, project, lookback_days)

        return {"project": project, "lookback_days": lookback_days, "modules": modules}
    except Exception as e:
        logger.error(f"Error clustering by module: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/failures/spikes")
async def get_failure_spikes(
    project: str = Query(..., description="Project name"),
    lookback_days: int = Query(7, ge=1, le=90),
    window_hours: int = Query(1, ge=1, le=24, description="Time window size in hours"),
    db: Session = Depends(get_db),
):
    """
    Detect failure spikes in time windows.

    **Parameters:**
    - **project**: Project name
    - **lookback_days**: Days to analyze
    - **window_hours**: Size of time window

    **Returns:**
    - Time windows with elevated failure rates
    """
    try:
        spikes = cluster_by_time(db, project, lookback_days, window_hours)

        return {
            "project": project,
            "lookback_days": lookback_days,
            "window_hours": window_hours,
            "spikes": spikes,
        }
    except Exception as e:
        logger.error(f"Error detecting spikes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/failures/related")
async def get_related_failures_endpoint(
    test_name: str = Query(..., description="Test name to find related failures for"),
    project: str = Query(..., description="Project name"),
    lookback_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """
    Find tests failing with similar errors.

    **Parameters:**
    - **test_name**: Test to find related failures for
    - **project**: Project name
    - **lookback_days**: Days to analyze

    **Returns:**
    - Tests with similar failure patterns
    """
    try:
        related = find_related_failures(db, test_name, project, lookback_days)

        return {
            "test": test_name,
            "project": project,
            "lookback_days": lookback_days,
            "related_failures": related,
        }
    except Exception as e:
        logger.error(f"Error finding related failures: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/history")
async def get_test_history(
    project: str = Query(..., description="Project name"),
    test_name: str = Query(..., description="Test name to get history for"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """
    Get execution history for a specific test.

    **Parameters:**
    - **project**: Project name
    - **test_name**: Full test name
    - **limit**: Maximum results to return (1-100)

    **Returns:**
    - List of test executions with timestamps, status, and duration
    """
    try:
        # Query test cases with their run information
        results = (
            db.query(TestCase, TestRun)
            .join(TestRun, TestCase.test_run_id == TestRun.id)
            .filter(TestRun.project == project)
            .filter(
                (TestCase.name == test_name)
                | (TestCase.classname + "::" + TestCase.name == test_name)
            )
            .order_by(TestRun.timestamp.desc())
            .limit(limit)
            .all()
        )

        history = []
        for test_case, test_run in results:
            history.append(
                {
                    "timestamp": test_run.timestamp.isoformat() if test_run.timestamp else None,
                    "status": test_case.status,
                    "duration_seconds": test_case.duration_seconds,
                    "branch": test_run.branch,
                    "commit_sha": test_run.commit_sha,
                    "error_message": test_case.error_message if test_case.status in ["failed", "error"] else None,
                }
            )

        return {
            "project": project,
            "test": test_name,
            "executions": len(history),
            "history": history,
        }
    except Exception as e:
        logger.error(f"Error retrieving test history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
