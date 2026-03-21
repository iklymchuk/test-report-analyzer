"""Tests for analysis modules."""

import pytest
from analysis.flaky_detector import detect_flaky_tests
from analysis.slow_detector import detect_slow_tests
from analysis.clustering import cluster_failures


def test_flaky_detector_function_exists():
    """Test that detect_flaky_tests function exists."""
    assert callable(detect_flaky_tests)


def test_slow_detector_function_exists():
    """Test that detect_slow_tests function exists."""
    assert callable(detect_slow_tests)


def test_failure_clusterer_function_exists():
    """Test that cluster_failures function exists."""
    assert callable(cluster_failures)


def test_analysis_modules_importable():
    """Test that all analysis modules can be imported."""
    import analysis.flaky_detector
    import analysis.slow_detector
    import analysis.clustering
    import analysis.trends

    assert analysis.flaky_detector is not None
    assert analysis.slow_detector is not None
    assert analysis.clustering is not None
    assert analysis.trends is not None
