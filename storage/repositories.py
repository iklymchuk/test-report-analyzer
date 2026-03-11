"""
Repository pattern implementation for data access.

This module provides a clean interface for CRUD operations on test data,
abstracting away the direct SQLAlchemy queries.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from storage.models import TestRun, TestCase


class TestRunRepository:
    """
    Repository for managing test run data.
    
    Provides methods to create, read, update, and query test runs.
    """
    
    def __init__(self, db: Session):
        """
        Initialize repository with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def create_test_run(self, data: Dict[str, Any]) -> TestRun:
        """
        Create a new test run with associated test cases.
        
        Args:
            data: Dictionary containing test_run and test_cases data
                  Format: {
                      'test_run': {...},
                      'test_cases': [...]
                  }
        
        Returns:
            Created TestRun object with associated test cases
            
        Example:
            data = {
                'test_run': {
                    'project': 'my-app',
                    'timestamp': datetime.now(),
                    'total_tests': 10,
                    ...
                },
                'test_cases': [
                    {'name': 'test_login', 'status': 'passed', ...},
                    ...
                ]
            }
            test_run = repo.create_test_run(data)
        """
        # Create test run
        test_run_data = data.get('test_run', {})
        
        # Filter to only valid TestRun fields (exclude extra fields from parser)
        valid_fields = {
            'timestamp', 'project', 'branch', 'commit_sha',
            'duration_seconds', 'total_tests', 'passed', 'failed', 
            'skipped', 'status'
        }
        filtered_data = {k: v for k, v in test_run_data.items() if k in valid_fields}
        
        test_run = TestRun(**filtered_data)
        
        # Add test run to session
        self.db.add(test_run)
        self.db.flush()  # Flush to get the test_run.id
        
        # Create associated test cases
        test_cases_data = data.get('test_cases', [])
        valid_case_fields = {
            'name', 'classname', 'duration_seconds', 'status',
            'error_message', 'error_type', 'stdout', 'stderr'
        }
        for case_data in test_cases_data:
            # Filter to only valid TestCase fields
            filtered_case = {k: v for k, v in case_data.items() if k in valid_case_fields}
            test_case = TestCase(
                test_run_id=test_run.id,
                **filtered_case
            )
            self.db.add(test_case)
        
        # Commit transaction
        self.db.commit()
        self.db.refresh(test_run)
        
        return test_run
    
    def get_by_id(self, test_run_id: int) -> Optional[TestRun]:
        """
        Get a test run by ID.
        
        Args:
            test_run_id: Test run ID
            
        Returns:
            TestRun object or None if not found
        """
        return self.db.query(TestRun).filter(TestRun.id == test_run_id).first()
    
    def get_recent(
        self,
        project: Optional[str] = None,
        branch: Optional[str] = None,
        limit: int = 50
    ) -> List[TestRun]:
        """
        Get recent test runs with optional filters.
        
        Args:
            project: Filter by project name
            branch: Filter by branch name
            limit: Maximum number of results
            
        Returns:
            List of TestRun objects ordered by timestamp (newest first)
        """
        query = self.db.query(TestRun)
        
        if project:
            query = query.filter(TestRun.project == project)
        if branch:
            query = query.filter(TestRun.branch == branch)
        
        return query.order_by(desc(TestRun.timestamp)).limit(limit).all()
    
    def get_by_project(
        self,
        project: str,
        days: int = 30,
        branch: Optional[str] = None
    ) -> List[TestRun]:
        """
        Get test runs for a project within a time window.
        
        Args:
            project: Project name
            days: Number of days to look back
            branch: Optional branch filter
            
        Returns:
            List of TestRun objects ordered by timestamp
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = self.db.query(TestRun).filter(
            TestRun.project == project,
            TestRun.timestamp >= cutoff
        )
        
        if branch:
            query = query.filter(TestRun.branch == branch)
        
        return query.order_by(TestRun.timestamp).all()
    
    def get_latest_by_project(self, project: str) -> Optional[TestRun]:
        """
        Get the most recent test run for a project.
        
        Args:
            project: Project name
            
        Returns:
            Latest TestRun object or None
        """
        return self.db.query(TestRun).filter(
            TestRun.project == project
        ).order_by(desc(TestRun.timestamp)).first()
    
    def count_by_project(self, project: str) -> int:
        """
        Count total test runs for a project.
        
        Args:
            project: Project name
            
        Returns:
            Count of test runs
        """
        return self.db.query(TestRun).filter(TestRun.project == project).count()
    
    def delete_old_runs(self, project: str, keep_days: int = 90) -> int:
        """
        Delete test runs older than specified days.
        
        Args:
            project: Project name
            keep_days: Number of days to keep
            
        Returns:
            Number of deleted test runs
        """
        cutoff = datetime.utcnow() - timedelta(days=keep_days)
        deleted = self.db.query(TestRun).filter(
            TestRun.project == project,
            TestRun.timestamp < cutoff
        ).delete()
        self.db.commit()
        return deleted


class TestCaseRepository:
    """
    Repository for managing test case data.
    
    Provides methods to query and analyze individual test cases.
    """
    
    def __init__(self, db: Session):
        """
        Initialize repository with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def get_by_id(self, test_case_id: int) -> Optional[TestCase]:
        """
        Get a test case by ID.
        
        Args:
            test_case_id: Test case ID
            
        Returns:
            TestCase object or None if not found
        """
        return self.db.query(TestCase).filter(TestCase.id == test_case_id).first()
    
    def get_by_test_run(self, test_run_id: int) -> List[TestCase]:
        """
        Get all test cases for a test run.
        
        Args:
            test_run_id: Test run ID
            
        Returns:
            List of TestCase objects
        """
        return self.db.query(TestCase).filter(
            TestCase.test_run_id == test_run_id
        ).all()
    
    def get_failed_tests(
        self,
        project: str,
        days: int = 7
    ) -> List[TestCase]:
        """
        Get failed test cases for a project within a time window.
        
        Args:
            project: Project name
            days: Number of days to look back
            
        Returns:
            List of failed TestCase objects
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.db.query(TestCase).join(TestRun).filter(
            TestRun.project == project,
            TestRun.timestamp >= cutoff,
            TestCase.status.in_(['failed', 'error'])
        ).all()
    
    def get_test_history(
        self,
        test_name: str,
        classname: Optional[str] = None,
        project: Optional[str] = None,
        limit: int = 20
    ) -> List[TestCase]:
        """
        Get execution history for a specific test.
        
        Args:
            test_name: Test name
            classname: Test class name (optional)
            project: Project name (optional)
            limit: Maximum number of results
            
        Returns:
            List of TestCase objects ordered by test run timestamp
        """
        query = self.db.query(TestCase).join(TestRun).filter(
            TestCase.name == test_name
        )
        
        if classname:
            query = query.filter(TestCase.classname == classname)
        if project:
            query = query.filter(TestRun.project == project)
        
        return query.order_by(desc(TestRun.timestamp)).limit(limit).all()
    
    def get_slow_tests(
        self,
        project: str,
        threshold_seconds: float = 5.0,
        min_runs: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get tests that exceed duration threshold (aggregate query).
        
        Args:
            project: Project name
            threshold_seconds: Duration threshold
            min_runs: Minimum number of runs to consider
            
        Returns:
            List of dictionaries with test statistics
        """
        results = self.db.query(
            TestCase.classname,
            TestCase.name,
            func.avg(TestCase.duration_seconds).label('avg_duration'),
            func.max(TestCase.duration_seconds).label('max_duration'),
            func.count(TestCase.id).label('run_count')
        ).join(TestRun).filter(
            TestRun.project == project
        ).group_by(
            TestCase.classname,
            TestCase.name
        ).having(
            func.avg(TestCase.duration_seconds) > threshold_seconds,
            func.count(TestCase.id) >= min_runs
        ).order_by(
            desc('avg_duration')
        ).all()
        
        return [
            {
                'classname': r.classname,
                'name': r.name,
                'full_name': f"{r.classname}::{r.name}" if r.classname else r.name,
                'avg_duration': round(r.avg_duration, 2),
                'max_duration': round(r.max_duration, 2),
                'run_count': r.run_count
            }
            for r in results
        ]
    
    def get_failure_stats(self, project: str, days: int = 30) -> Dict[str, Any]:
        """
        Get failure statistics for a project.
        
        Args:
            project: Project name
            days: Number of days to analyze
            
        Returns:
            Dictionary with failure statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        total_tests = self.db.query(TestCase).join(TestRun).filter(
            TestRun.project == project,
            TestRun.timestamp >= cutoff
        ).count()
        
        failed_tests = self.db.query(TestCase).join(TestRun).filter(
            TestRun.project == project,
            TestRun.timestamp >= cutoff,
            TestCase.status.in_(['failed', 'error'])
        ).count()
        
        return {
            'total_tests': total_tests,
            'failed_tests': failed_tests,
            'failure_rate': round((failed_tests / total_tests * 100), 2) if total_tests > 0 else 0
        }


def bulk_create_test_cases(db: Session, test_run_id: int, test_cases: List[Dict[str, Any]]) -> int:
    """
    Bulk insert test cases for better performance.
    
    Args:
        db: Database session
        test_run_id: Parent test run ID
        test_cases: List of test case dictionaries
        
    Returns:
        Number of test cases created
    """
    objects = [
        TestCase(test_run_id=test_run_id, **case_data)
        for case_data in test_cases
    ]
    
    db.bulk_save_objects(objects)
    db.commit()
    
    return len(objects)
