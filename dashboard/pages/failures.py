"""
Failure Analysis Page

Clusters and analyzes test failures to identify patterns.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from collections import Counter


def render(api_url: str, project: str, days: int):
    """Render the failure analysis page."""

    st.header("❌ Failure Analysis")
    st.markdown(
        """
    Analyze test failures to identify patterns, common root causes, and systemic issues.
    """
    )

    # Configuration
    col1, col2 = st.columns(2)

    with col1:
        lookback_days = st.slider(
            "Analysis Period (days)",
            min_value=1,
            max_value=days,
            value=min(7, days),
            help="Number of days to analyze for failure patterns",
        )

    with col2:
        min_cluster_size = st.number_input(
            "Minimum Cluster Size",
            min_value=1,
            max_value=10,
            value=2,
            help="Minimum number of failures to form a cluster",
        )

    st.divider()

    # Fetch failure clusters
    try:
        response = requests.get(
            f"{api_url}/api/v1/failures/clusters",
            params={"project": project, "lookback_days": lookback_days},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            clusters = data.get("clusters", [])

            # Filter by minimum cluster size
            clusters = [c for c in clusters if c.get("count", 0) >= min_cluster_size]

            if clusters:
                st.warning(f"Found {len(clusters)} failure cluster(s)")

                # Summary metrics
                total_failures = sum(c.get("count", 0) for c in clusters)
                total_affected_tests = len(
                    set(test for c in clusters for test in c.get("affected_tests", []))
                )

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Failure Clusters", len(clusters))

                with col2:
                    st.metric("Total Failures", total_failures)

                with col3:
                    st.metric("Affected Tests", total_affected_tests)

                st.divider()

                # Cluster size distribution
                st.subheader("📊 Cluster Size Distribution")

                cluster_sizes = [c.get("count", 0) for c in clusters]

                fig = px.bar(
                    x=[f"Cluster {i+1}" for i in range(len(clusters))],
                    y=cluster_sizes,
                    title="Number of Failures per Cluster",
                    labels={"x": "Cluster", "y": "Failure Count"},
                    color=cluster_sizes,
                    color_continuous_scale="Reds",
                )

                fig.update_layout(showlegend=False, height=350)
                st.plotly_chart(fig, use_container_width=True)

                st.divider()

                # Detailed cluster analysis
                st.subheader("🔍 Failure Clusters")

                for i, cluster in enumerate(clusters, 1):
                    pattern = cluster.get("pattern", "Unknown Pattern")
                    count = cluster.get("count", 0)
                    affected_tests = cluster.get("affected_tests", [])
                    sample_error = cluster.get(
                        "sample_error", "No error message available"
                    )

                    # Determine severity
                    if count >= 10:
                        severity_icon = "🔴"
                        severity_label = "CRITICAL"
                    elif count >= 5:
                        severity_icon = "🟠"
                        severity_label = "HIGH"
                    else:
                        severity_icon = "🟡"
                        severity_label = "MEDIUM"

                    with st.expander(
                        f"{severity_icon} **Cluster {i}: {pattern}** ({count} failures, {len(affected_tests)} tests)",
                        expanded=(i <= 3),  # Expand first 3 clusters
                    ):
                        # Cluster details
                        col_a, col_b = st.columns([1, 2])

                        with col_a:
                            st.write(f"**Severity:** {severity_icon} {severity_label}")
                            st.write(f"**Failure Count:** {count}")
                            st.write(f"**Affected Tests:** {len(affected_tests)}")

                        with col_b:
                            st.write(f"**Error Pattern:** `{pattern}`")

                        st.divider()

                        # Affected tests
                        st.write("**Affected Tests:**")

                        # Show all tests or limit to first 10
                        display_limit = 10
                        for test in affected_tests[:display_limit]:
                            st.write(f"- `{test}`")

                        if len(affected_tests) > display_limit:
                            st.write(
                                f"*... and {len(affected_tests) - display_limit} more*"
                            )

                        st.divider()

                        # Sample error message
                        st.write("**Sample Error Message:**")
                        st.code(sample_error, language="text")

                        st.divider()

                        # Root cause suggestions
                        st.write("**💡 Potential Root Causes:**")

                        # Pattern-based suggestions
                        pattern_lower = pattern.lower()

                        if "timeout" in pattern_lower or "timed out" in pattern_lower:
                            st.info(
                                """
                            - Network latency or slow external services
                            - Database query performance issues
                            - Insufficient timeout values in test configuration
                            - Resource contention in test environment
                            """
                            )
                        elif "null" in pattern_lower or "none" in pattern_lower:
                            st.info(
                                """
                            - Missing test data or fixtures
                            - Uninitialized variables or objects
                            - Race condition in test setup
                            - Improper cleanup from previous tests
                            """
                            )
                        elif (
                            "connection" in pattern_lower or "connect" in pattern_lower
                        ):
                            st.info(
                                """
                            - External service unavailable
                            - Network configuration issues
                            - Connection pool exhaustion
                            - Firewall or security restrictions
                            """
                            )
                        elif (
                            "assertion" in pattern_lower or "expected" in pattern_lower
                        ):
                            st.info(
                                """
                            - Test expectations may be too strict
                            - Environment-specific differences
                            - Data inconsistency issues
                            - Recent code changes affecting behavior
                            """
                            )
                        elif "permission" in pattern_lower or "access" in pattern_lower:
                            st.info(
                                """
                            - File system permission issues
                            - Database access rights problems
                            - Authentication/authorization failures
                            - Environment configuration differences
                            """
                            )
                        else:
                            st.info(
                                """
                            - Review recent code changes that may have introduced this error
                            - Check test environment configuration
                            - Verify test data and dependencies
                            - Consider adding more detailed error logging
                            """
                            )

                        # Recommended actions
                        st.write("**🎯 Recommended Actions:**")

                        if count >= 10:
                            st.error(
                                """
                            1. **IMMEDIATE**: Assign to team for investigation
                            2. Review recent deployments and configuration changes
                            3. Add monitoring/alerts for this error pattern
                            4. Consider temporarily disabling affected tests if blocking CI
                            5. Root cause analysis session with team
                            """
                            )
                        elif count >= 5:
                            st.warning(
                                """
                            1. Schedule investigation within 1-2 days
                            2. Review error logs and stack traces
                            3. Check if error is environment-specific
                            4. Add retry logic if intermittent
                            5. Update test documentation with findings
                            """
                            )
                        else:
                            st.success(
                                """
                            1. Monitor for increasing frequency
                            2. Document error for future reference
                            3. Consider adding test logging for root cause
                            4. Review during next sprint planning
                            """
                            )

                st.divider()

                # Additional insights
                st.subheader("📈 Failure Trends")

                try:
                    anomalies_response = requests.get(
                        f"{api_url}/api/v1/anomalies/{project}",
                        params={"days": lookback_days},
                        timeout=5,
                    )

                    if anomalies_response.status_code == 200:
                        anomalies = anomalies_response.json().get("anomalies", [])

                        if anomalies:
                            st.warning(
                                f"Detected {len(anomalies)} anomaly(ies) in test behavior"
                            )

                            for anomaly in anomalies[:5]:  # Show top 5
                                test_name = anomaly.get("test", "Unknown")
                                anomaly_type = anomaly.get("type", "Unknown")
                                description = anomaly.get(
                                    "description", "No description"
                                )

                                with st.expander(f"⚠️ {test_name} - {anomaly_type}"):
                                    st.write(description)

                                    if "current_value" in anomaly:
                                        st.write(
                                            f"**Current Value:** {anomaly['current_value']}"
                                        )
                                    if "baseline" in anomaly:
                                        st.write(f"**Baseline:** {anomaly['baseline']}")
                                    if "deviation" in anomaly:
                                        st.write(
                                            f"**Deviation:** {anomaly['deviation']}"
                                        )
                        else:
                            st.success("No anomalies detected in recent test behavior")

                except Exception:
                    pass

            else:
                st.success("🎉 No significant failure patterns detected!")
                st.balloons()
                st.info(
                    "This is great! Your tests are failing for diverse reasons, suggesting good test coverage without systemic issues."
                )

        else:
            st.error(f"Failed to fetch failure clusters: HTTP {response.status_code}")

    except requests.exceptions.Timeout:
        st.error("⏱️ Request timed out. The API may be slow or unreachable.")
    except requests.exceptions.ConnectionError:
        st.error(
            "🔌 Cannot connect to API. Please check the API URL and ensure the service is running."
        )
    except Exception as e:
        st.error(f"❌ Error loading failure analysis: {str(e)}")

    st.divider()

    # Recent failures summary
    st.subheader("📋 Recent Failed Tests")

    try:
        # Get recent runs and filter for failures
        runs_response = requests.get(
            f"{api_url}/api/v1/runs", params={"project": project, "limit": 5}, timeout=5
        )

        if runs_response.status_code == 200:
            recent_runs = runs_response.json()

            failed_test_names = []

            for run in recent_runs:
                run_id = run.get("id")
                if run_id and run.get("failed", 0) > 0:
                    # Get failed tests from this run
                    tests_response = requests.get(
                        f"{api_url}/api/v1/runs/{run_id}/tests",
                        params={"status": "failed"},
                        timeout=5,
                    )

                    if tests_response.status_code == 200:
                        tests = tests_response.json().get("tests", [])
                        for test in tests:
                            test_name = test.get("name", "Unknown")
                            classname = test.get("classname", "")
                            full_name = (
                                f"{classname}::{test_name}" if classname else test_name
                            )
                            failed_test_names.append(full_name)

            if failed_test_names:
                # Count frequency
                failure_counts = Counter(failed_test_names)

                st.write(
                    f"**Most Frequently Failing Tests (Last {len(recent_runs)} runs):**"
                )

                df_failures = pd.DataFrame(
                    failure_counts.most_common(15), columns=["Test", "Failure Count"]
                )

                fig = px.bar(
                    df_failures,
                    x="Failure Count",
                    y="Test",
                    orientation="h",
                    title="Most Common Failures",
                    color="Failure Count",
                    color_continuous_scale="Reds",
                )

                fig.update_layout(
                    height=400, yaxis={"categoryorder": "total ascending"}
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("No failures in recent test runs!")

    except Exception as e:
        st.warning(f"Could not load recent failures: {str(e)}")
