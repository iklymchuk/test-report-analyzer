"""
Flaky Test Detection Module.

This module identifies tests with inconsistent results across multiple runs.
A test is considered flaky if it sometimes passes and sometimes fails without
code changes, indicating non-deterministic behavior.

Algorithm:
1. Query recent test runs for a project
2. Group test results by test name
3. Calculate flakiness score (failures / total runs)
4. Detect status transitions (PASS → FAIL or FAIL → PASS)
5. Flag tests with scores between 0.1 and 0.9 (not consistently passing/failing)
"""

from typing import List, Dict, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import desc

from storage.models import TestRun, TestCase


def detect_flaky_tests(
    db: Session,
    project: str,
    lookback_runs: int = 20,
    min_runs: int = 3,
    min_flakiness: float = 0.1,
    max_flakiness: float = 0.9
) -> List[Dict]:
    """
    Identify tests with inconsistent results across multiple runs.
    
    A test is considered flaky if:
    - It has been run at least `min_runs` times
    - Its failure rate is between `min_flakiness` and `max_flakiness`
    - It has at least one status transition (pass→fail or fail→pass)
    
    Args:
        db: Database session
        project: Project name to analyze
        lookback_runs: Number of recent test runs to examine
        min_runs: Minimum number of runs required to consider a test
        min_flakiness: Minimum flakiness score (0.0-1.0)
        max_flakiness: Maximum flakiness score (0.0-1.0)
        
    Returns:
        List of flaky test dictionaries with metadata, sorted by flakiness score
        
    Example:
        ```python
        db = SessionLocal()
        flaky_tests = detect_flaky_tests(db, "my-app", lookback_runs=30)
        
        for test in flaky_tests:
            print(f"{test['test']}: {test['flakiness_score']*100:.1f}% flaky")
            print(f"  Recent pattern: {test['recent_pattern']}")
        ```
    """
    # Get recent test runs for the project
    recent_runs = db.query(TestRun).filter(
        TestRun.project == project
    ).order_by(desc(TestRun.timestamp)).limit(lookback_runs).all()
    
    if not recent_runs:
        return []
    
    run_ids = [run.id for run in recent_runs]
    
    # Get all test cases from these runs
    test_cases = db.query(TestCase).filter(
        TestCase.test_run_id.in_(run_ids)
    ).order_by(TestCase.test_run_id).all()
    
    # Group results by test (using classname::name as key)
    test_results = defaultdict(list)
    
    for case in test_cases:
        # Create unique test identifier
        test_key = _make_test_key(case.classname, case.name)
        test_results[test_key].append({
            'status': case.status,
            'test_run_id': case.test_run_id,
            'duration': case.duration_seconds
        })
    
    # Analyze each test for flakiness
    flaky_tests = []
    
    for test_key, results in test_results.items():
        if len(results) < min_runs:
            # Not enough data to determine flakiness
            continue
        
        # Calculate flakiness metrics
        total_runs = len(results)
        statuses = [r['status'] for r in results]
        
        failures = sum(1 for s in statuses if s in ['failed', 'error'])
        passes = sum(1 for s in statuses if s == 'passed')
        skipped = sum(1 for s in statuses if s == 'skipped')
        
        # Skip tests that are always skipped
        if skipped == total_runs:
            continue
        
        # Calculate flakiness score (ratio of failures to total runs)
        flakiness_score = failures / total_runs
        
        # Check if flakiness is in the target range
        if not (min_flakiness < flakiness_score < max_flakiness):
            continue
        
        # Check for status transitions (key indicator of flakiness)
        has_transitions = _detect_transitions(statuses)
        
        if not has_transitions:
            continue
        
        # Calculate additional metrics
        avg_duration = sum(r['duration'] for r in results if r['duration']) / len([r for r in results if r['duration']]) if any(r['duration'] for r in results) else 0
        
        # Create recent pattern visualization (last 10 runs)
        recent_statuses = statuses[-10:]
        recent_pattern = ''.join([_status_to_char(s) for s in recent_statuses])
        
        flaky_tests.append({
            'test': test_key,
            'flakiness_score': round(flakiness_score, 3),
            'total_runs': total_runs,
            'failures': failures,
            'passes': passes,
            'skipped': skipped,
            'recent_pattern': recent_pattern,
            'avg_duration': round(avg_duration, 3) if avg_duration else 0,
            'transitions': _count_transitions(statuses)
        })
    
    # Sort by flakiness score (descending)
    return sorted(flaky_tests, key=lambda x: x['flakiness_score'], reverse=True)


def get_flaky_test_details(
    db: Session,
    test_name: str,
    project: str,
    lookback_runs: int = 50
) -> Optional[Dict]:
    """
    Get detailed information about a specific flaky test.
    
    Args:
        db: Database session
        test_name: Full test identifier (classname::name)
        project: Project name
        lookback_runs: Number of recent runs to examine
        
    Returns:
        Dictionary with detailed test history and statistics
        
    Example:
        ```python
        details = get_flaky_test_details(
            db, 
            "tests.api.test_auth::test_login",
            "my-app"
        )
        print(f"First failure: {details['first_failure_date']}")
        print(f"Last success: {details['last_success_date']}")
        ```
    """
    # Parse test name
    if '::' in test_name:
        classname, name = test_name.split('::', 1)
    else:
        classname = None
        name = test_name
    
    # Get recent test runs
    recent_runs = db.query(TestRun).filter(
        TestRun.project == project
    ).order_by(desc(TestRun.timestamp)).limit(lookback_runs).all()
    
    if not recent_runs:
        return None
    
    run_ids = [run.id for run in recent_runs]
    
    # Get test cases matching this test
    query = db.query(TestCase, TestRun).join(TestRun).filter(
        TestCase.test_run_id.in_(run_ids),
        TestCase.name == name
    )
    
    if classname:
        query = query.filter(TestCase.classname == classname)
    
    results = query.order_by(TestRun.timestamp).all()
    
    if not results:
        return None
    
    # Compile statistics
    statuses = [case.status for case, _ in results]
    timestamps = [run.timestamp for _, run in results]
    durations = [case.duration_seconds for case, _ in results]
    errors = [case.error_message for case, _ in results if case.status in ['failed', 'error']]
    
    failures = sum(1 for s in statuses if s in ['failed', 'error'])
    passes = sum(1 for s in statuses if s == 'passed')
    
    # Find first/last occurrences
    first_failure = next((ts for s, ts in zip(statuses, timestamps) if s in ['failed', 'error']), None)
    last_success = next((ts for s, ts in zip(reversed(statuses), reversed(timestamps)) if s == 'passed'), None)
    
    return {
        'test': test_name,
        'project': project,
        'total_runs': len(results),
        'failures': failures,
        'passes': passes,
        'flakiness_score': round(failures / len(results), 3) if results else 0,
        'first_failure_date': first_failure.isoformat() if first_failure else None,
        'last_success_date': last_success.isoformat() if last_success else None,
        'avg_duration': round(sum(d for d in durations if d) / len([d for d in durations if d]), 3) if any(durations) else 0,
        'status_history': statuses,
        'recent_errors': errors[-5:] if errors else [],
        'transitions': _count_transitions(statuses)
    }


def _make_test_key(classname: Optional[str], name: str) -> str:
    """Create unique test identifier."""
    if classname:
        return f"{classname}::{name}"
    return name


def _status_to_char(status: str) -> str:
    """Convert status to single character for pattern visualization."""
    if status in ['failed', 'error']:
        return 'F'
    elif status == 'passed':
        return 'P'
    elif status == 'skipped':
        return 'S'
    else:
        return '?'


def _detect_transitions(statuses: List[str]) -> bool:
    """
    Detect if there are any status transitions in the sequence.
    
    A transition is when a test changes from passed to failed/error or vice versa.
    """
    for i in range(len(statuses) - 1):
        current = statuses[i]
        next_status = statuses[i + 1]
        
        # Check for meaningful transitions (not involving skipped)
        if current == 'passed' and next_status in ['failed', 'error']:
            return True
        if current in ['failed', 'error'] and next_status == 'passed':
            return True
    
    return False


def _count_transitions(statuses: List[str]) -> int:
    """Count the number of status transitions."""
    count = 0
    for i in range(len(statuses) - 1):
        current = statuses[i]
        next_status = statuses[i + 1]
        
        if current == 'passed' and next_status in ['failed', 'error']:
            count += 1
        elif current in ['failed', 'error'] and next_status == 'passed':
            count += 1
    
    return count


def get_flaky_test_summary(db: Session, project: str, lookback_runs: int = 20) -> Dict:
    """
    Get high-level summary of flaky test situation for a project.
    
    Args:
        db: Database session
        project: Project name
        lookback_runs: Number of recent runs to examine
        
    Returns:
        Summary dictionary with counts and statistics
        
    Example:
        ```python
        summary = get_flaky_test_summary(db, "my-app")
        print(f"Total flaky tests: {summary['total_flaky']}")
        print(f"Critical (>50% flaky): {summary['critical_count']}")
        ```
    """
    flaky_tests = detect_flaky_tests(db, project, lookback_runs)
    
    if not flaky_tests:
        return {
            'project': project,
            'total_flaky': 0,
            'critical_count': 0,
            'moderate_count': 0,
            'mild_count': 0,
            'avg_flakiness': 0,
            'most_flaky': None
        }
    
    # Categorize by severity
    critical = [t for t in flaky_tests if t['flakiness_score'] >= 0.5]
    moderate = [t for t in flaky_tests if 0.3 <= t['flakiness_score'] < 0.5]
    mild = [t for t in flaky_tests if t['flakiness_score'] < 0.3]
    
    avg_flakiness = sum(t['flakiness_score'] for t in flaky_tests) / len(flaky_tests)
    
    return {
        'project': project,
        'total_flaky': len(flaky_tests),
        'critical_count': len(critical),
        'moderate_count': len(moderate),
        'mild_count': len(mild),
        'avg_flakiness': round(avg_flakiness, 3),
        'most_flaky': flaky_tests[0] if flaky_tests else None
    }
