"""
JUnit XML test report parser.

This module parses JUnit XML format test reports, which are the standard
output format for most testing frameworks (pytest, JUnit, Maven, etc.).
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path


class JUnitParserError(Exception):
    """Custom exception for JUnit parsing errors."""
    pass


def parse_junit_xml(file_path: str, project: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse a JUnit XML test report file.
    
    Args:
        file_path: Path to the JUnit XML file
        project: Optional project name to include in the result
        
    Returns:
        Dictionary containing test_run and test_cases data:
        {
            'test_run': {
                'timestamp': datetime,
                'project': str,
                'total_tests': int,
                'passed': int,
                'failed': int,
                'skipped': int,
                'duration_seconds': float,
                'status': str
            },
            'test_cases': [
                {
                    'name': str,
                    'classname': str,
                    'duration_seconds': float,
                    'status': str,
                    'error_message': str (optional),
                    'error_type': str (optional)
                },
                ...
            ]
        }
        
    Raises:
        JUnitParserError: If the file cannot be parsed
        FileNotFoundError: If the file does not exist
        
    Example:
        >>> data = parse_junit_xml('test-results.xml', project='my-app')
        >>> print(f"Total tests: {data['test_run']['total_tests']}")
        >>> print(f"Failed: {data['test_run']['failed']}")
    """
    # Validate file exists
    if not Path(file_path).exists():
        raise FileNotFoundError(f"Test report file not found: {file_path}")
    
    try:
        # Parse XML
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise JUnitParserError(f"Invalid XML format: {e}")
    
    # Handle both <testsuite> and <testsuites> root elements
    if root.tag == 'testsuites':
        # Multiple test suites - aggregate results
        return _parse_testsuites(root, project)
    elif root.tag == 'testsuite':
        # Single test suite
        return _parse_testsuite(root, project)
    else:
        raise JUnitParserError(
            f"Unexpected root element: {root.tag}. "
            f"Expected 'testsuite' or 'testsuites'"
        )


def _parse_testsuites(root: ET.Element, project: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse XML with <testsuites> root (multiple test suites).
    
    Args:
        root: XML root element
        project: Optional project name
        
    Returns:
        Dictionary with test_run and test_cases data
    """
    # Aggregate metrics across all suites
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    total_time = 0.0
    all_test_cases = []
    
    # Process each test suite
    for testsuite in root.findall('testsuite'):
        suite_data = _parse_testsuite(testsuite, project)
        
        # Aggregate counts
        total_tests += suite_data['test_run']['total_tests']
        total_failures += suite_data['test_run'].get('failures', 0)
        total_errors += suite_data['test_run'].get('errors', 0)
        total_skipped += suite_data['test_run']['skipped']
        total_time += suite_data['test_run']['duration_seconds']
        
        # Collect all test cases
        all_test_cases.extend(suite_data['test_cases'])
    
    # Calculate passed tests
    total_failed = total_failures + total_errors
    passed = total_tests - total_failed - total_skipped
    
    # Determine overall status
    status = 'success' if total_failed == 0 else 'failure'
    
    return {
        'test_run': {
            'timestamp': datetime.now(),
            'project': project,
            'total_tests': total_tests,
            'passed': passed,
            'failed': total_failed,
            'skipped': total_skipped,
            'duration_seconds': total_time,
            'status': status
        },
        'test_cases': all_test_cases
    }


def _parse_testsuite(root: ET.Element, project: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse a single <testsuite> element.
    
    Args:
        root: testsuite XML element
        project: Optional project name
        
    Returns:
        Dictionary with test_run and test_cases data
    """
    # Extract test suite attributes
    attribs = root.attrib
    
    # Get counts from attributes
    total_tests = int(attribs.get('tests', 0))
    failures = int(attribs.get('failures', 0))
    errors = int(attribs.get('errors', 0))
    skipped = int(attribs.get('skipped', attribs.get('skip', 0)))
    time_seconds = float(attribs.get('time', 0))
    
    # Calculate passed tests
    total_failed = failures + errors
    passed = total_tests - total_failed - skipped
    
    # Determine status
    status = 'success' if total_failed == 0 else 'failure'
    
    # Parse timestamp if available
    timestamp_str = attribs.get('timestamp')
    if timestamp_str:
        try:
            # Try ISO format first
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            # Fall back to current time
            timestamp = datetime.now()
    else:
        timestamp = datetime.now()
    
    # Extract test cases
    test_cases = []
    for testcase in root.findall('testcase'):
        test_case_data = _parse_testcase(testcase)
        if test_case_data:  # Filter out None results
            test_cases.append(test_case_data)
    
    return {
        'test_run': {
            'timestamp': timestamp,
            'project': project,
            'total_tests': total_tests,
            'passed': passed,
            'failed': total_failed,
            'skipped': skipped,
            'duration_seconds': time_seconds,
            'status': status,
            'failures': failures,  # Keep for aggregation
            'errors': errors
        },
        'test_cases': test_cases
    }


def _parse_testcase(testcase: ET.Element) -> Optional[Dict[str, Any]]:
    """
    Parse a single <testcase> element.
    
    Args:
        testcase: testcase XML element
        
    Returns:
        Dictionary with test case data or None if invalid
    """
    attribs = testcase.attrib
    
    # Test name is required
    name = attribs.get('name')
    if not name:
        return None
    
    # Extract test case data
    test_data = {
        'name': name,
        'classname': attribs.get('classname', ''),
        'duration_seconds': float(attribs.get('time', 0))
    }
    
    # Check for failure, error, or skipped elements
    failure = testcase.find('failure')
    error = testcase.find('error')
    skipped = testcase.find('skipped')
    
    if failure is not None:
        test_data['status'] = 'failed'
        test_data['error_message'] = _get_text_content(failure)
        test_data['error_type'] = failure.attrib.get('type', 'Failure')
    elif error is not None:
        test_data['status'] = 'error'
        test_data['error_message'] = _get_text_content(error)
        test_data['error_type'] = error.attrib.get('type', 'Error')
    elif skipped is not None:
        test_data['status'] = 'skipped'
        test_data['error_message'] = _get_text_content(skipped)
    else:
        test_data['status'] = 'passed'
    
    # Optionally capture stdout/stderr
    system_out = testcase.find('system-out')
    if system_out is not None:
        test_data['stdout'] = _get_text_content(system_out)
    
    system_err = testcase.find('system-err')
    if system_err is not None:
        test_data['stderr'] = _get_text_content(system_err)
    
    return test_data


def _get_text_content(element: ET.Element) -> str:
    """
    Extract text content from an XML element.
    
    Args:
        element: XML element
        
    Returns:
        Text content or empty string
    """
    if element is None:
        return ''
    
    # Try getting text directly
    text = element.text or ''
    
    # Also check for message attribute (some formats use this)
    if not text and 'message' in element.attrib:
        text = element.attrib['message']
    
    return text.strip()


def validate_junit_xml(file_path: str) -> bool:
    """
    Validate if a file is a valid JUnit XML report.
    
    Args:
        file_path: Path to the XML file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        parse_junit_xml(file_path)
        return True
    except (JUnitParserError, FileNotFoundError, ET.ParseError):
        return False


def get_junit_summary(file_path: str) -> str:
    """
    Get a human-readable summary of a JUnit report.
    
    Args:
        file_path: Path to the JUnit XML file
        
    Returns:
        Summary string
        
    Example:
        >>> print(get_junit_summary('test-results.xml'))
        Test Summary:
        Total: 100 | Passed: 95 | Failed: 3 | Skipped: 2
        Pass Rate: 95.0%
        Duration: 45.2s
    """
    try:
        data = parse_junit_xml(file_path)
        test_run = data['test_run']
        
        total = test_run['total_tests']
        passed = test_run['passed']
        failed = test_run['failed']
        skipped = test_run['skipped']
        duration = test_run['duration_seconds']
        
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        summary = f"""Test Summary:
Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}
Pass Rate: {pass_rate:.1f}%
Duration: {duration:.1f}s"""
        
        return summary
    except Exception as e:
        return f"Error reading test report: {e}"


class JUnitParser:
    """
    JUnit XML parser class.
    
    Provides an object-oriented interface to the JUnit parsing functions.
    """
    
    def parse_file(self, file_path: str, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse a JUnit XML file.
        
        Args:
            file_path: Path to the JUnit XML file
            project: Optional project name
            
        Returns:
            Dictionary with test_run and test_cases data
        """
        return parse_junit_xml(file_path, project)


if __name__ == "__main__":
    # Simple CLI for testing the parser
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python junit_parser.py <junit-xml-file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    try:
        print(get_junit_summary(file_path))
        print("\n" + "="*50 + "\n")
        
        data = parse_junit_xml(file_path)
        print(f"Parsed {len(data['test_cases'])} test cases")
        
        # Show failed tests
        failed_tests = [tc for tc in data['test_cases'] if tc['status'] in ['failed', 'error']]
        if failed_tests:
            print(f"\nFailed Tests ({len(failed_tests)}):")
            for test in failed_tests[:5]:  # Show first 5
                print(f"  - {test.get('classname', '')}::{test['name']}")
                if test.get('error_message'):
                    error_preview = test['error_message'][:100]
                    print(f"    Error: {error_preview}...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
