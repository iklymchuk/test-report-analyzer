"""
Trends API Routes.

Endpoints for time-series analysis, trends, and anomaly detection.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
import logging

from storage.database import SessionLocal
from analysis.trends import (
    get_daily_trends,
    get_weekly_trends,
    detect_anomalies,
    calculate_moving_average,
    compare_time_periods,
    get_failure_rate_trend,
    get_duration_trend,
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


@router.get("/daily")
async def get_daily_trend_data(
    project: str = Query(..., description="Project name"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
):
    """
    Get daily test execution trends.

    **Parameters:**
    - **project**: Project name
    - **days**: Number of days to look back (1-365)

    **Returns:**
    - Daily aggregated test statistics
    """
    try:
        trends = get_daily_trends(db, project, days=days)

        return {
            "project": project,
            "days": days,
            "data_points": len(trends),
            "trends": trends,
        }
    except Exception as e:
        logger.error(f"Error getting daily trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weekly")
async def get_weekly_trend_data(
    project: str = Query(..., description="Project name"),
    weeks: int = Query(12, ge=1, le=104, description="Number of weeks to analyze"),
    db: Session = Depends(get_db),
):
    """
    Get weekly test execution trends.

    **Parameters:**
    - **project**: Project name
    - **weeks**: Number of weeks to look back (1-104)

    **Returns:**
    - Weekly aggregated test statistics
    """
    try:
        trends = get_weekly_trends(db, project, weeks=weeks)

        return {
            "project": project,
            "weeks": weeks,
            "data_points": len(trends),
            "trends": trends,
        }
    except Exception as e:
        logger.error(f"Error getting weekly trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies")
async def detect_trend_anomalies(
    project: str = Query(..., description="Project name"),
    days: int = Query(30, ge=7, le=365, description="Days to analyze"),
    std_threshold: float = Query(
        2.0, ge=0.5, le=5.0, description="Z-score threshold for anomalies"
    ),
    db: Session = Depends(get_db),
):
    """
    Detect anomalies in test metrics using statistical analysis.

    **Parameters:**
    - **project**: Project name
    - **days**: Days to analyze
    - **std_threshold**: Z-score threshold (higher = fewer anomalies)

    **Returns:**
    - Detected anomalies with z-scores and severity
    """
    try:
        anomalies = detect_anomalies(
            db, project, days=days, std_threshold=std_threshold
        )

        return {
            "project": project,
            "days": days,
            "std_threshold": std_threshold,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
        }
    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/moving-average")
async def get_moving_average_data(
    project: str = Query(..., description="Project name"),
    days: int = Query(30, ge=7, le=365, description="Days to analyze"),
    window: int = Query(7, ge=2, le=30, description="Moving average window size"),
    db: Session = Depends(get_db),
):
    """
    Calculate moving average for smoothed trend visualization.

    **Parameters:**
    - **project**: Project name
    - **days**: Days to analyze
    - **window**: Moving average window (e.g., 7 for 7-day MA)

    **Returns:**
    - Original and smoothed data points
    """
    try:
        ma_data = calculate_moving_average(db, project, days=days, window=window)

        return {"project": project, "days": days, "window": window, "data": ma_data}
    except Exception as e:
        logger.error(f"Error calculating moving average: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare")
async def compare_periods(
    project: str = Query(..., description="Project name"),
    period1_days: int = Query(7, ge=1, le=90, description="Recent period in days"),
    period2_days: int = Query(
        30, ge=1, le=365, description="Comparison period in days"
    ),
    gap_days: int = Query(0, ge=0, le=90, description="Gap between periods"),
    db: Session = Depends(get_db),
):
    """
    Compare metrics between two time periods.

    **Parameters:**
    - **project**: Project name
    - **period1_days**: Recent period (e.g., last 7 days)
    - **period2_days**: Comparison baseline (e.g., last 30 days)
    - **gap_days**: Days between periods (default: 0)

    **Returns:**
    - Comparison with % changes and trends
    """
    try:
        comparison = compare_time_periods(
            db,
            project,
            period1_days=period1_days,
            period2_days=period2_days,
            gap_days=gap_days,
        )

        return {
            "project": project,
            "period1_days": period1_days,
            "period2_days": period2_days,
            "gap_days": gap_days,
            "comparison": comparison,
        }
    except Exception as e:
        logger.error(f"Error comparing periods: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/failure-rate")
async def get_failure_rate_trend_data(
    project: str = Query(..., description="Project name"),
    days: int = Query(30, ge=1, le=365, description="Days to analyze"),
    db: Session = Depends(get_db),
):
    """
    Get failure rate trends over time.

    **Parameters:**
    - **project**: Project name
    - **days**: Days to analyze

    **Returns:**
    - Failure rate trend analysis
    """
    try:
        trends = get_failure_rate_trend(db, project, days=days)

        return {"project": project, "days": days, "trends": trends}
    except Exception as e:
        logger.error(f"Error getting failure rate trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/duration")
async def get_duration_trend_data(
    project: str = Query(..., description="Project name"),
    days: int = Query(30, ge=1, le=365, description="Days to analyze"),
    db: Session = Depends(get_db),
):
    """
    Get test duration trends over time.

    **Parameters:**
    - **project**: Project name
    - **days**: Days to analyze

    **Returns:**
    - Duration trend analysis
    """
    try:
        trends = get_duration_trend(db, project, days=days)

        return {"project": project, "days": days, "trends": trends}
    except Exception as e:
        logger.error(f"Error getting duration trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_trends_summary(
    project: str = Query(..., description="Project name"),
    days: int = Query(30, ge=7, le=365, description="Days to analyze"),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive trends summary.

    Returns aggregated trend data for dashboards.

    **Parameters:**
    - **project**: Project name
    - **days**: Days to analyze

    **Returns:**
    - Multi-metric trend summary with key indicators
    """
    try:
        # Get daily trends
        daily_trends = get_daily_trends(db, project, days=days)

        # Detect anomalies for failure rates
        anomalies = detect_anomalies(db, project, days=days, std_threshold=2.5)

        # Compare recent vs historical
        comparison = compare_time_periods(
            db, project, period1_days=7, period2_days=days
        )

        # Get failure rate trends
        failure_trends = get_failure_rate_trend(db, project, days=days)

        return {
            "project": project,
            "days": days,
            "summary": {
                "data_points": len(daily_trends),
                "anomaly_count": len(anomalies),
                "recent_vs_historical": comparison,
                "daily_trends": (
                    daily_trends[-14:] if len(daily_trends) > 14 else daily_trends
                ),  # Last 2 weeks
                "failure_rate_trend": failure_trends,
            },
        }
    except Exception as e:
        logger.error(f"Error generating trends summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health-score")
async def get_project_health_score(
    project: str = Query(..., description="Project name"),
    days: int = Query(7, ge=1, le=30, description="Days to evaluate"),
    db: Session = Depends(get_db),
):
    """
    Calculate project health score based on recent trends.

    Composite metric from failure rate, test count, and stability.

    **Parameters:**
    - **project**: Project name
    - **days**: Days to evaluate (1-30)

    **Returns:**
    - Health score (0-100) with breakdown
    """
    try:
        trends = get_daily_trends(db, project, days=days)

        if not trends:
            raise HTTPException(
                status_code=404, detail=f"No data found for project '{project}'"
            )

        # Calculate health components
        total_runs = sum(t.get("runs", 0) for t in trends)

        # Initialize variables with defaults
        avg_failure_rate = 0.0
        consistency_score = 30.0
        activity_score = 0.0
        health_score = 0.0

        if total_runs == 0:
            health_score = 0
        else:
            # Success rate (0-40 points)
            avg_failure_rate = sum(t.get("failure_rate", 0) for t in trends) / len(
                trends
            )
            success_score = min(40, (1 - avg_failure_rate / 100) * 40)

            # Consistency (0-30 points) - low variance is good
            failure_rates = [t.get("failure_rate", 0) for t in trends]
            if len(failure_rates) > 1:
                variance = sum(
                    (r - avg_failure_rate) ** 2 for r in failure_rates
                ) / len(failure_rates)
                consistency_score = max(0, 30 - (variance * 0.3))
            else:
                consistency_score = 30

            # Activity (0-30 points)
            avg_runs_per_day = total_runs / days
            activity_score = min(30, avg_runs_per_day * 3)

            health_score = success_score + consistency_score + activity_score

        # Determine grade
        if health_score >= 90:
            grade = "A"
        elif health_score >= 80:
            grade = "B"
        elif health_score >= 70:
            grade = "C"
        elif health_score >= 60:
            grade = "D"
        else:
            grade = "F"

        return {
            "project": project,
            "days": days,
            "health_score": round(health_score, 1),
            "grade": grade,
            "breakdown": {
                "success_rate": (
                    round(1 - (avg_failure_rate / 100), 3) if total_runs > 0 else 0
                ),
                "consistency": round(consistency_score / 30, 3),
                "activity": round(activity_score / 30, 3),
                "total_runs": total_runs,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating health score: {e}")
        raise HTTPException(status_code=500, detail=str(e))
