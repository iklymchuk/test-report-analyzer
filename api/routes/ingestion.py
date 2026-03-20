"""
Ingestion API Routes.

Endpoints for uploading and processing test reports.
"""

from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
    File,
    Form,
    Depends,
    BackgroundTasks,
)
from sqlalchemy.orm import Session
from pathlib import Path
import logging
import tempfile
import shutil
from typing import Optional

from storage.database import SessionLocal
from storage.repositories import TestRunRepository
from storage.models import TestRun
from ingestion.junit_parser import JUnitParser

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def process_report_file(
    file_path: str, project: str, branch: str, build_id: Optional[str], db: Session
) -> dict:
    """
    Process a test report file and store results.

    Args:
        file_path: Path to the report file
        project: Project name
        branch: Git branch
        build_id: CI build identifier
        db: Database session

    Returns:
        Processing result with statistics
    """
    try:
        # Parse the report
        parser = JUnitParser()
        data = parser.parse_file(file_path, project)

        # Update metadata
        test_run_data = data["test_run"]
        test_run_data["project"] = project
        test_run_data["branch"] = branch
        # Note: build_id not yet supported in model, can be added later

        # Store in database
        repo = TestRunRepository(db)
        test_run = repo.create_test_run(data)

        logger.info(
            f"Processed report for {project}/{branch}: "
            f"{test_run.total_tests} tests, "
            f"{test_run.failed} failures"
        )

        return {
            "success": True,
            "test_run_id": test_run.id,
            "project": test_run.project,
            "branch": test_run.branch,
            "build_id": build_id,
            "timestamp": test_run.timestamp.isoformat(),
            "statistics": {
                "total_tests": test_run.total_tests,
                "passed_tests": test_run.passed,
                "failed_tests": test_run.failed,
                "skipped_tests": test_run.skipped,
                "error_tests": 0,  # Not tracked separately yet
                "total_duration": test_run.duration_seconds,
            },
        }
    except Exception as e:
        logger.error(f"Error processing report: {e}")
        raise


async def process_report_async(
    temp_file: str, project: str, branch: str, build_id: Optional[str]
) -> None:
    """
    Background task to process report asynchronously.

    Args:
        temp_file: Temporary file path
        project: Project name
        branch: Git branch
        build_id: CI build identifier
    """
    db = SessionLocal()
    try:
        process_report_file(temp_file, project, branch, build_id, db)
    except Exception as e:
        logger.error(f"Background processing failed: {e}")
    finally:
        db.close()
        # Clean up temp file
        try:
            Path(temp_file).unlink()
        except Exception as e:
            logger.warning(f"Failed to delete temp file {temp_file}: {e}")


@router.post("/ingest")
async def ingest_report(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="JUnit XML test report file"),
    project: str = Form(..., description="Project name"),
    branch: str = Form(default="main", description="Git branch"),
    build_id: Optional[str] = Form(default=None, description="CI build identifier"),
    async_processing: bool = Form(default=False, description="Process in background"),
    db: Session = Depends(get_db),
):
    """
    Upload and process a test report.
    
    **Parameters:**
    - **file**: JUnit XML file to upload
    - **project**: Project name (required)
    - **branch**: Git branch (default: "main")
    - **build_id**: CI build identifier (optional)
    - **async_processing**: Process in background (default: false)
    
    **Returns:**
    - Processing result with test statistics
    
    **Example curl:**
    ```bash
    curl -X POST http://localhost:8000/api/v1/ingest \\
      -F "file=@tests/fixtures/sample_report.xml" \\
      -F "project=my-service" \\
      -F "branch=main" \\
      -F "build_id=12345"
    ```
    """
    # Validate file type
    if not file.filename.endswith((".xml", ".junit")):
        raise HTTPException(
            status_code=400, detail="File must be a JUnit XML report (.xml or .junit)"
        )

    # Save uploaded file to temporary location
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_file = tmp.name
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Process synchronously or asynchronously
    if async_processing:
        # Add to background tasks
        background_tasks.add_task(
            process_report_async, temp_file, project, branch, build_id
        )

        return {
            "success": True,
            "message": "Report queued for processing",
            "project": project,
            "branch": branch,
            "build_id": build_id,
            "async": True,
        }
    else:
        # Process immediately
        try:
            result = process_report_file(temp_file, project, branch, build_id, db)
            return result
        except Exception as e:
            logger.error(f"Error processing report: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # Clean up temp file
            try:
                Path(temp_file).unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_file}: {e}")


@router.post("/ingest/batch")
async def ingest_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(..., description="Multiple JUnit XML files"),
    project: str = Form(..., description="Project name"),
    branch: str = Form(default="main", description="Git branch"),
    build_id: Optional[str] = Form(default=None, description="CI build identifier"),
    db: Session = Depends(get_db),
):
    """
    Upload and process multiple test reports in batch.
    
    All reports are processed asynchronously in the background.
    
    **Parameters:**
    - **files**: Multiple JUnit XML files
    - **project**: Project name (required)
    - **branch**: Git branch (default: "main")
    - **build_id**: CI build identifier (optional)
    
    **Returns:**
    - Batch processing confirmation
    
    **Example curl:**
    ```bash
    curl -X POST http://localhost:8000/api/v1/ingest/batch \\
      -F "files=@report1.xml" \\
      -F "files=@report2.xml" \\
      -F "project=my-service" \\
      -F "branch=main"
    ```
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > 50:
        raise HTTPException(
            status_code=400, detail="Maximum 50 files allowed per batch"
        )

    # Validate all files
    for file in files:
        if not file.filename.endswith((".xml", ".junit")):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.filename}. Must be JUnit XML.",
            )

    # Save all files and queue for processing
    queued_files = []
    try:
        for file in files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
                shutil.copyfileobj(file.file, tmp)
                temp_file = tmp.name

                # Add to background tasks
                background_tasks.add_task(
                    process_report_async, temp_file, project, branch, build_id
                )

                queued_files.append({"filename": file.filename, "temp_path": temp_file})
    except Exception as e:
        logger.error(f"Failed to save batch files: {e}")
        # Clean up any saved files
        for item in queued_files:
            try:
                Path(item["temp_path"]).unlink()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Failed to save batch files")

    return {
        "success": True,
        "message": f"{len(queued_files)} reports queued for processing",
        "project": project,
        "branch": branch,
        "build_id": build_id,
        "files": [item["filename"] for item in queued_files],
    }


@router.get("/runs")
async def get_test_runs(
    project: Optional[str] = None,
    branch: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Get test runs with optional filtering.

    **Parameters:**
    - **project**: Filter by project name (optional)
    - **branch**: Filter by branch (optional)
    - **limit**: Maximum runs to return (default: 50, max: 200)
    - **offset**: Pagination offset (default: 0)

    **Returns:**
    - List of test runs with metadata
    """
    if limit > 200:
        limit = 200

    try:
        query = db.query(TestRun)

        if project:
            query = query.filter(TestRun.project == project)
        if branch:
            query = query.filter(TestRun.branch == branch)

        total = query.count()

        runs = (
            query.order_by(TestRun.timestamp.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return [
            {
                "id": run.id,
                "project": run.project,
                "branch": run.branch,
                "commit_sha": run.commit_sha,
                "timestamp": run.timestamp.isoformat() if run.timestamp else None,
                "total_tests": run.total_tests,
                "passed": run.passed,
                "failed": run.failed,
                "skipped": run.skipped,
                "duration_seconds": run.duration_seconds,
                "status": run.status,
            }
            for run in runs
        ]
    except Exception as e:
        logger.error(f"Error retrieving test runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}")
async def get_test_run(
    run_id: int, include_test_cases: bool = False, db: Session = Depends(get_db)
):
    """
    Get a specific test run by ID.

    **Parameters:**
    - **run_id**: Test run ID
    - **include_test_cases**: Include individual test cases (default: false)

    **Returns:**
    - Test run details with optional test cases
    """
    repo = TestRunRepository(db)

    try:
        run = repo.get_by_id(run_id)

        if not run:
            raise HTTPException(status_code=404, detail=f"Test run {run_id} not found")

        result = {
            "id": run.id,
            "project": run.project,
            "branch": run.branch,
            "build_id": run.build_id,
            "timestamp": run.timestamp.isoformat(),
            "total_tests": run.total_tests,
            "passed_tests": run.passed_tests,
            "failed_tests": run.failed_tests,
            "skipped_tests": run.skipped_tests,
            "error_tests": run.error_tests,
            "total_duration": run.total_duration,
        }

        if include_test_cases:
            result["test_cases"] = [
                {
                    "name": tc.name,
                    "classname": tc.classname,
                    "status": tc.status,
                    "duration": tc.duration,
                    "error_message": tc.error_message,
                    "error_type": tc.error_type,
                    "stacktrace": tc.stacktrace,
                }
                for tc in run.test_cases
            ]

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving test run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/runs/{run_id}")
async def delete_test_run(run_id: int, db: Session = Depends(get_db)):
    """
    Delete a test run and its test cases.

    **Parameters:**
    - **run_id**: Test run ID to delete

    **Returns:**
    - Deletion confirmation
    """
    repo = TestRunRepository(db)

    try:
        run = repo.get_by_id(run_id)

        if not run:
            raise HTTPException(status_code=404, detail=f"Test run {run_id} not found")

        repo.delete(run_id)

        return {
            "success": True,
            "message": f"Test run {run_id} deleted",
            "run_id": run_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting test run: {e}")
        raise HTTPException(status_code=500, detail=str(e))
