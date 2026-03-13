#!/usr/bin/env python3
"""
Script to generate sample test data for analysis demonstration.

This script ingests the sample test report multiple times with variations
to create historical data that demonstrates:
- Flaky tests (tests that sometimes pass, sometimes fail)
- Slow tests
- Failure patterns
- Trends over time
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ingestion.junit_parser import parse_junit_xml
from storage.database import SessionLocal, init_db
from storage.repositories import TestRunRepository


def generate_sample_data(num_runs: int = 30):
    """
    Generate sample test data by ingesting reports with variations.
    
    Args:
        num_runs: Number of test runs to generate
    """
    print("Generating sample test data...")
    print(f"Creating {num_runs} test runs with variations\n")
    
    db = SessionLocal()
    repo = TestRunRepository(db)
    
    # Base timestamp (30 days ago)
    base_time = datetime.utcnow() - timedelta(days=30)
    
    # Tests that will be flaky (sometimes pass, sometimes fail)
    flaky_tests = [
        'test_login_with_valid_credentials',
        'test_payment_gateway_timeout',
        'test_database_connection'
    ]
    
    for i in range(num_runs):
        print(f"Creating run {i+1}/{num_runs}...")
        
        # Parse the sample report
        data = parse_junit_xml('tests/fixtures/sample_report.xml')
        
        # Adjust timestamp (spread over 30 days)
        timestamp = base_time + timedelta(days=i, hours=random.randint(0, 23))
        data['test_run']['timestamp'] = timestamp
        data['test_run']['project'] = 'demo'
        data['test_run']['branch'] = random.choice(['main', 'main', 'main', 'feature/new-api', 'feature/refactor'])
        data['test_run']['commit_sha'] = f"abc{i:04d}{'0' * 36}"[:40]
        
        # Introduce variations to create patterns
        
        # 1. Make some tests flaky
        for test_case in data['test_cases']:
            if test_case['name'] in flaky_tests:
                # Randomly change status to create flakiness
                if random.random() < 0.3:  # 30% chance to flip status
                    if test_case['status'] == 'passed':
                        test_case['status'] = 'failed'
                        test_case['error_type'] = random.choice(['TimeoutError', 'ConnectionError', 'AssertionError'])
                        test_case['error_message'] = f"{test_case['error_type']}: Flaky failure at run {i+1}"
                    elif test_case['status'] in ['failed', 'error']:
                        test_case['status'] = 'passed'
                        test_case['error_type'] = None
                        test_case['error_message'] = None
        
        # 2. Gradually increase duration for some tests (performance regression)
        for test_case in data['test_cases']:
            if 'generate_monthly_report' in test_case['name']:
                # Increase duration over time
                factor = 1.0 + (i / num_runs) * 0.5  # Up to 50% slower
                if test_case['duration_seconds']:
                    test_case['duration_seconds'] *= factor
        
        # 3. Create a spike in failures midway through
        if 15 <= i <= 18:
            for test_case in data['test_cases']:
                if random.random() < 0.3 and test_case['status'] == 'passed':
                    test_case['status'] = 'failed'
                    test_case['error_type'] = 'DeploymentError'
                    test_case['error_message'] = 'DeploymentError: Database migration failed during deployment'
        
        # 4. Recalculate test run metrics
        test_run = data['test_run']
        statuses = [tc['status'] for tc in data['test_cases']]
        test_run['passed'] = sum(1 for s in statuses if s == 'passed')
        test_run['failed'] = sum(1 for s in statuses if s in ['failed', 'error'])
        test_run['skipped'] = sum(1 for s in statuses if s == 'skipped')
        test_run['status'] = 'success' if test_run['failed'] == 0 else 'failure'
        test_run['duration_seconds'] = sum(tc.get('duration_seconds', 0) or 0 for tc in data['test_cases'])
        
        # Store in database
        try:
            repo.create_test_run(data)
            print(f"  ✓ Run {i+1}: {test_run['passed']}/{test_run['total_tests']} passed, "
                  f"{test_run['failed']} failed, {test_run['duration_seconds']:.2f}s")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    db.close()
    print(f"\n✓ Generated {num_runs} test runs successfully!")


if __name__ == "__main__":
    # Ensure database is initialized
    try:
        init_db()
    except:
        pass  # May already be initialized
    
    # Generate sample data
    generate_sample_data(30)
