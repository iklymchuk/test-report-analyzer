#!/usr/bin/env python3
"""
Sample script to ingest a JUnit XML test report into the database.

This script demonstrates the complete ingestion workflow:
1. Parse JUnit XML file
2. Create database session
3. Store test run and test cases
4. Display summary

Usage:
    python ingest_report.py <junit-xml-file> [--project PROJECT] [--branch BRANCH] [--commit COMMIT]

Example:
    python ingest_report.py test-results.xml --project my-app --branch main --commit abc123
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ingestion.junit_parser import parse_junit_xml, get_junit_summary, JUnitParserError
from storage.database import SessionLocal, init_db
from storage.repositories import TestRunRepository


def ingest_test_report(
    file_path: str,
    project: str = None,
    branch: str = None,
    commit_sha: str = None
) -> bool:
    """
    Ingest a JUnit XML test report into the database.
    
    Args:
        file_path: Path to JUnit XML file
        project: Project name (optional)
        branch: Git branch name (optional)
        commit_sha: Git commit SHA (optional)
        
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"Ingesting Test Report: {file_path}")
    print(f"{'='*60}\n")
    
    # Step 1: Parse the JUnit XML file
    print("Step 1: Parsing JUnit XML...")
    try:
        data = parse_junit_xml(file_path, project=project)
        print(f"✓ Successfully parsed {len(data['test_cases'])} test cases")
    except FileNotFoundError:
        print(f"✗ Error: File not found: {file_path}")
        return False
    except JUnitParserError as e:
        print(f"✗ Error parsing JUnit XML: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    
    # Add metadata to test run
    test_run = data['test_run']
    if project:
        test_run['project'] = project
    if branch:
        test_run['branch'] = branch
    if commit_sha:
        test_run['commit_sha'] = commit_sha
    
    # Set default project if not provided
    if not test_run.get('project'):
        test_run['project'] = 'default-project'
        print("  ⚠ No project specified, using 'default-project'")
    
    # Display summary
    print(f"\nTest Run Summary:")
    print(f"  Project: {test_run['project']}")
    print(f"  Branch: {test_run.get('branch', 'N/A')}")
    print(f"  Commit: {test_run.get('commit_sha', 'N/A')}")
    print(f"  Timestamp: {test_run['timestamp']}")
    print(f"  Total Tests: {test_run['total_tests']}")
    print(f"  Passed: {test_run['passed']} ({test_run['passed']/test_run['total_tests']*100:.1f}%)")
    print(f"  Failed: {test_run['failed']}")
    print(f"  Skipped: {test_run['skipped']}")
    print(f"  Duration: {test_run['duration_seconds']:.2f}s")
    print(f"  Status: {test_run['status']}")
    
    # Step 2: Store in database
    print(f"\nStep 2: Storing in database...")
    try:
        db = SessionLocal()
        repo = TestRunRepository(db)
        
        # Create test run with test cases
        created_run = repo.create_test_run(data)
        
        print(f"✓ Successfully stored test run (ID: {created_run.id})")
        print(f"  - Test run record created")
        print(f"  - {len(data['test_cases'])} test case records created")
        
        db.close()
    except Exception as e:
        print(f"✗ Error storing in database: {e}")
        print(f"  Make sure the database is initialized (run: python storage/database.py)")
        return False
    
    # Step 3: Show some statistics
    print(f"\nStep 3: Analysis...")
    
    # Show failed tests
    failed_tests = [tc for tc in data['test_cases'] if tc['status'] in ['failed', 'error']]
    if failed_tests:
        print(f"\n⚠ Failed Tests ({len(failed_tests)}):")
        for test in failed_tests[:5]:  # Show first 5
            full_name = f"{test.get('classname', '')}::{test['name']}"
            print(f"  - {full_name}")
            if test.get('error_type'):
                print(f"    Type: {test['error_type']}")
            if test.get('error_message'):
                error_preview = test['error_message'].split('\n')[0][:80]
                print(f"    Error: {error_preview}...")
        
        if len(failed_tests) > 5:
            print(f"  ... and {len(failed_tests) - 5} more")
    else:
        print("\n✓ All tests passed!")
    
    # Show slow tests (>5 seconds)
    slow_tests = [tc for tc in data['test_cases'] if tc.get('duration_seconds', 0) > 5.0]
    if slow_tests:
        print(f"\n🐌 Slow Tests (>5s) ({len(slow_tests)}):")
        for test in sorted(slow_tests, key=lambda x: x['duration_seconds'], reverse=True)[:5]:
            full_name = f"{test.get('classname', '')}::{test['name']}"
            print(f"  - {full_name}: {test['duration_seconds']:.2f}s")
    
    print(f"\n{'='*60}")
    print(f"✓ Ingestion Complete!")
    print(f"{'='*60}\n")
    
    return True


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Ingest JUnit XML test reports into the database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic ingestion
  python ingest_report.py test-results.xml
  
  # With project metadata
  python ingest_report.py test-results.xml --project my-app --branch main
  
  # Full metadata
  python ingest_report.py test-results.xml \\
    --project my-app \\
    --branch feature/new-feature \\
    --commit abc123def456
        """
    )
    
    parser.add_argument(
        'file',
        help='Path to JUnit XML test report file'
    )
    parser.add_argument(
        '--project',
        help='Project name (e.g., "my-app")',
        default=None
    )
    parser.add_argument(
        '--branch',
        help='Git branch name (e.g., "main", "develop")',
        default=None
    )
    parser.add_argument(
        '--commit',
        help='Git commit SHA',
        default=None
    )
    parser.add_argument(
        '--init-db',
        action='store_true',
        help='Initialize database before ingestion'
    )
    
    args = parser.parse_args()
    
    # Initialize database if requested
    if args.init_db:
        print("Initializing database...")
        init_db()
        print()
    
    # Ingest the report
    success = ingest_test_report(
        file_path=args.file,
        project=args.project,
        branch=args.branch,
        commit_sha=args.commit
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
