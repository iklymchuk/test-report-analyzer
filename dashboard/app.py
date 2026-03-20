"""
Test Report Analyzer - Interactive Dashboard

A Streamlit-based dashboard for visualizing test health metrics, flaky tests,
slow tests, and failure patterns.
"""

import streamlit as st
import requests
from datetime import datetime
import os

# Page configuration
st.set_page_config(
    page_title="Test Report Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .success-box {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #28a745;
    }
    .warning-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ffc107;
    }
    .error-box {
        background-color: #f8d7da;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #dc3545;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize session state
if "api_url" not in st.session_state:
    st.session_state.api_url = os.getenv(
        "TEST_ANALYZER_API_URL", "http://localhost:8000"
    )

if "project" not in st.session_state:
    st.session_state.project = "demo"

# Sidebar configuration
with st.sidebar:
    st.title("⚙️ Configuration")

    # API URL configuration
    api_url = st.text_input(
        "API URL",
        value=st.session_state.api_url,
        help="Base URL of the Test Analyzer API",
    )
    st.session_state.api_url = api_url

    st.divider()

    # Project selection
    st.subheader("📁 Project Selection")

    # Try to get available projects
    try:
        response = requests.get(f"{api_url}/api/v1/stats", timeout=2)
        if response.status_code == 200:
            stats = response.json()
            projects = stats.get("projects", [])
            if projects:
                project_names = [p["name"] for p in projects]
                selected_project = st.selectbox(
                    "Select Project",
                    options=project_names,
                    index=(
                        project_names.index(st.session_state.project)
                        if st.session_state.project in project_names
                        else 0
                    ),
                )
                st.session_state.project = selected_project
            else:
                st.session_state.project = st.text_input(
                    "Project Name", value=st.session_state.project
                )
        else:
            st.session_state.project = st.text_input(
                "Project Name", value=st.session_state.project
            )
    except Exception:
        st.session_state.project = st.text_input(
            "Project Name", value=st.session_state.project
        )

    st.divider()

    # Time range filter
    st.subheader("📅 Time Range")
    days = st.slider(
        "Lookback Days",
        min_value=7,
        max_value=90,
        value=30,
        step=1,
        help="Number of days to include in analysis",
    )

    st.divider()

    # API health check
    st.subheader("🔌 API Status")
    try:
        response = requests.get(f"{api_url}/health", timeout=2)
        if response.status_code == 200:
            health = response.json()
            if health.get("status") == "healthy":
                st.success("✅ Connected")
                st.caption(f"Version: {health.get('version', 'unknown')}")
            else:
                st.error("⚠️ Degraded")
        else:
            st.error("❌ Unavailable")
    except Exception as e:
        st.error("❌ Disconnected")
        st.caption(str(e))

    st.divider()

    # Refresh button
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

# Main navigation
st.title("📊 Test Report Analyzer")
st.markdown(f"**Project:** `{st.session_state.project}` | **Period:** Last {days} days")

# Page navigation using tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📈 Overview",
        "🔄 Flaky Tests",
        "🐌 Slow Tests",
        "❌ Failure Analysis",
        "🤖 AI Insights",
    ]
)


# Store common data in session state to avoid redundant API calls
@st.cache_data(ttl=60)
def fetch_data(api_url: str, endpoint: str, params: dict = None):
    """Fetch data from API with caching."""
    try:
        response = requests.get(f"{api_url}{endpoint}", params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch data from {endpoint}: {str(e)}")
        return None


# Import page modules
try:
    from pages import overview, flaky, slow, failures, ai_insights

    with tab1:
        overview.render(st.session_state.api_url, st.session_state.project, days)

    with tab2:
        flaky.render(st.session_state.api_url, st.session_state.project, days)

    with tab3:
        slow.render(st.session_state.api_url, st.session_state.project, days)

    with tab4:
        failures.render(st.session_state.api_url, st.session_state.project, days)

    with tab5:
        ai_insights.render(st.session_state.api_url, st.session_state.project, days)

except ImportError:
    # Fallback: show basic content in each tab
    with tab1:
        st.info(
            "Overview page module not found. Please ensure all page modules are installed."
        )

    with tab2:
        st.info("Flaky tests page module not found.")

    with tab3:
        st.info("Slow tests page module not found.")

    with tab4:
        st.info("Failure analysis page module not found.")

    with tab5:
        st.info("AI insights page module not found.")

# Footer
st.divider()
st.caption(
    f"Test Report Analyzer Dashboard • Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
