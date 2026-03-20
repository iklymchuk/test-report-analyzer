"""
Shared utilities for the dashboard.
"""

import streamlit as st
from typing import Any, Dict, Optional
import requests


def safe_api_call(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
) -> Optional[Dict]:
    """
    Make a safe API call with error handling.

    Args:
        url: API endpoint URL
        method: HTTP method (GET, POST, etc.)
        params: Query parameters
        timeout: Request timeout in seconds

    Returns:
        Response JSON or None if failed
    """
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, timeout=timeout)
        else:
            response = requests.post(url, json=params, timeout=timeout)

        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        st.error("⏱️ Request timed out. The API may be slow or unreachable.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 Cannot connect to API. Please check the API URL.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ API error: {e.response.status_code}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None


def format_duration(seconds: float) -> str:
    """
    Format duration in a human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format a value as a percentage.

    Args:
        value: Value to format (0-100 or 0-1)
        decimals: Number of decimal places

    Returns:
        Formatted percentage string
    """
    if value > 1:
        return f"{value:.{decimals}f}%"
    else:
        return f"{value * 100:.{decimals}f}%"


def get_status_color(status: str) -> str:
    """
    Get color for a test status.

    Args:
        status: Test status (passed, failed, skipped, etc.)

    Returns:
        Color name or hex code
    """
    status_colors = {
        "passed": "green",
        "failed": "red",
        "error": "red",
        "skipped": "gray",
        "flaky": "orange",
    }
    return status_colors.get(status.lower(), "blue")


def get_severity_color(score: float) -> str:
    """
    Get color based on severity score.

    Args:
        score: Severity score (0-1 or 0-100)

    Returns:
        Color name or hex code
    """
    # Normalize to 0-100 range
    if score <= 1:
        score *= 100

    if score >= 80:
        return "green"
    elif score >= 60:
        return "yellow"
    elif score >= 40:
        return "orange"
    else:
        return "red"


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def create_metric_card(
    title: str, value: Any, delta: Optional[Any] = None, icon: str = "📊"
):
    """
    Create a styled metric card.

    Args:
        title: Metric title
        value: Metric value
        delta: Optional delta/change value
        icon: Optional icon emoji
    """
    st.markdown(
        f"""
    <div style="background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem; text-align: center;">
        <div style="font-size: 2rem;">{icon}</div>
        <div style="font-size: 0.875rem; color: #6c757d;">{title}</div>
        <div style="font-size: 1.5rem; font-weight: bold;">{value}</div>
        {f'<div style="font-size: 0.875rem; color: #28a745;">{delta}</div>' if delta else ''}
    </div>
    """,
        unsafe_allow_html=True,
    )


def show_info_box(message: str, type: str = "info"):
    """
    Show a styled info box.

    Args:
        message: Message to display
        type: Box type (info, success, warning, error)
    """
    colors = {
        "info": {"bg": "#d1ecf1", "border": "#0c5460"},
        "success": {"bg": "#d4edda", "border": "#155724"},
        "warning": {"bg": "#fff3cd", "border": "#856404"},
        "error": {"bg": "#f8d7da", "border": "#721c24"},
    }

    color = colors.get(type, colors["info"])

    st.markdown(
        f"""
    <div style="background-color: {color['bg']}; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid {color['border']};">
        {message}
    </div>
    """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300)  # Cache for 5 minutes
def cached_api_call(
    url: str, params: Optional[Dict[str, Any]] = None
) -> Optional[Dict]:
    """
    Make a cached API call.

    Args:
        url: API endpoint URL
        params: Query parameters

    Returns:
        Response JSON or None if failed
    """
    return safe_api_call(url, params=params)
