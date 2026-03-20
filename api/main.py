"""
Test Report Analyzer API.

FastAPI application for ingesting test reports and providing analysis endpoints.
This API exposes all the analysis capabilities built in Part 1 and Part 2.

Features:
- Test report ingestion
- Flaky test detection
- Slow test analysis
- Failure clustering
- Trend analysis
- Health monitoring
"""

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import logging
import os

from storage.database import SessionLocal, init_db
from storage.models import TestRun
from api.routes import analysis, ingestion, trends

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Test Report Analyzer API",
    description="Automated test analysis and insights for development teams",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis.router, prefix="/api/v1", tags=["Analysis"])
app.include_router(ingestion.router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(trends.router, prefix="/api/v1/trends", tags=["Trends"])

# Dependency to get database session
def get_db():
    """
    Database session dependency.

    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Add shorthand routes for dashboard compatibility
from api.routes.trends import get_project_health_score, get_daily_trend_data, detect_trend_anomalies


@app.get("/api/v1/health-score/{project}", tags=["Trends"])
async def health_score_shorthand(
    project: str,
    lookback_days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Shorthand endpoint for health score (dashboard compatibility)."""
    return await get_project_health_score(project=project, days=lookback_days, db=db)


@app.get("/api/v1/trends/{project}", tags=["Trends"])
async def trends_shorthand(
    project: str, days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)
):
    """Shorthand endpoint for daily trends (dashboard compatibility)."""
    result = await get_daily_trend_data(project=project, days=days, db=db)
    return {
        "project": project,
        "days": days,
        "data_points": result.get("trends", []),
        "trend_direction": "stable",  # Simple placeholder
    }


@app.get("/api/v1/anomalies/{project}", tags=["Trends"])
async def anomalies_shorthand(
    project: str,
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Shorthand endpoint for anomalies (dashboard compatibility)."""
    return await detect_trend_anomalies(project=project, days=days, std_threshold=2.0, db=db)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    logger.info("Starting Test Report Analyzer API...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Test Report Analyzer API...")


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.

    Returns:
        API metadata and available endpoints
    """
    return {
        "name": "Test Report Analyzer API",
        "version": "1.0.0",
        "status": "running",
        "description": "Automated test analysis and insights",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "ingestion": "/api/v1/ingest",
            "test_runs": "/api/v1/runs",
            "flaky_tests": "/api/v1/tests/flaky",
            "slow_tests": "/api/v1/tests/slow",
            "failure_clusters": "/api/v1/failures/clusters",
            "trends": "/api/v1/trends/{project}",
        },
    }


@app.get("/health", tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint.

    Checks database connectivity and returns system status.

    Returns:
        Health status including database connectivity
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
        raise HTTPException(status_code=503, detail="Database unavailable")

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "version": "1.0.0",
    }


@app.get("/api/v1/stats", tags=["Statistics"])
async def get_statistics(db: Session = Depends(get_db)):
    """
    Get overall API statistics.

    Returns:
        System-wide statistics
    """
    try:
        total_runs = db.query(TestRun).count()

        # Get project count
        projects = db.query(TestRun.project).distinct().all()
        project_count = len(projects)

        # Get latest run
        latest_run = db.query(TestRun).order_by(TestRun.timestamp.desc()).first()

        return {
            "total_test_runs": total_runs,
            "total_projects": project_count,
            "projects": [p[0] for p in projects],
            "latest_run": (
                {
                    "project": latest_run.project if latest_run else None,
                    "timestamp": (
                        latest_run.timestamp.isoformat() if latest_run else None
                    ),
                    "total_tests": latest_run.total_tests if latest_run else 0,
                }
                if latest_run
                else None
            ),
        }
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


if __name__ == "__main__":
    import uvicorn

    # Get configuration from environment
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"

    uvicorn.run("api.main:app", host=host, port=port, reload=reload, log_level="info")
