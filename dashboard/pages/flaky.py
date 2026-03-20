"""
Flaky Tests Page

Identifies and displays tests with inconsistent results.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px


def render(api_url: str, project: str, days: int):
    """Render the flaky tests page."""

    st.header("🔄 Flaky Test Detection")
    st.markdown(
        """
    Flaky tests are tests that produce inconsistent results - sometimes passing, sometimes failing
    without any code changes. They reduce confidence in your test suite and waste developer time.
    """
    )

    # Configuration
    col1, col2, col3 = st.columns(3)

    with col1:
        min_runs = st.number_input(
            "Minimum Runs",
            min_value=2,
            max_value=100,
            value=5,
            help="Minimum number of runs to consider for flakiness detection",
        )

    with col2:
        min_flakiness = st.slider(
            "Min Flakiness Score",
            min_value=0.0,
            max_value=1.0,
            value=0.1,
            step=0.05,
            help="Minimum flakiness score to display (0.0 = never flaky, 1.0 = always flaky)",
        )

    with col3:
        sort_by = st.selectbox(
            "Sort By",
            options=["Flakiness Score", "Failure Count", "Test Name"],
            index=0,
        )

    st.divider()

    # Fetch flaky tests
    try:
        response = requests.get(
            f"{api_url}/api/v1/tests/flaky",
            params={"project": project, "lookback_days": days, "min_runs": min_runs},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            flaky_tests = data.get("flaky_tests", [])

            # Filter by minimum flakiness
            flaky_tests = [
                t for t in flaky_tests if t.get("flakiness_score", 0) >= min_flakiness
            ]

            if flaky_tests:
                st.success(f"Found {len(flaky_tests)} flaky test(s) matching criteria")

                # Convert to DataFrame
                df = pd.DataFrame(flaky_tests)

                # Sort
                if sort_by == "Flakiness Score":
                    df = df.sort_values("flakiness_score", ascending=False)
                elif sort_by == "Failure Count":
                    df = df.sort_values("failures", ascending=False)
                else:
                    df = df.sort_values("test", ascending=True)

                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Total Flaky Tests", len(df))

                with col2:
                    avg_flakiness = df["flakiness_score"].mean()
                    st.metric("Avg Flakiness", f"{avg_flakiness:.2f}")

                with col3:
                    high_flakiness = len(df[df["flakiness_score"] >= 0.3])
                    st.metric("High Flakiness (≥0.3)", high_flakiness)

                with col4:
                    total_failures = df["failures"].sum()
                    st.metric("Total Failures", int(total_failures))

                st.divider()

                # Visualization: Top 10 Flaky Tests
                st.subheader("📊 Top 10 Flaky Tests")

                df_top = df.head(10).copy()

                # Shorten test names for display
                df_top["short_name"] = df_top["test"].apply(
                    lambda x: x.split("::")[-1] if "::" in x else x[-50:]
                )

                fig = px.bar(
                    df_top,
                    y="short_name",
                    x="flakiness_score",
                    orientation="h",
                    title="Flakiness Score by Test",
                    labels={"short_name": "Test", "flakiness_score": "Flakiness Score"},
                    color="flakiness_score",
                    color_continuous_scale="Reds",
                    text="flakiness_score",
                )

                fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
                fig.update_layout(
                    height=400,
                    showlegend=False,
                    yaxis={"categoryorder": "total ascending"},
                )

                st.plotly_chart(fig, use_container_width=True)

                st.divider()

                # Detailed Table
                st.subheader("📋 Detailed Flaky Test List")

                # Prepare display dataframe
                df_display = df.copy()

                # Add severity indicator
                def severity(score):
                    if score >= 0.5:
                        return "🔴 Critical"
                    elif score >= 0.3:
                        return "🟠 High"
                    elif score >= 0.15:
                        return "🟡 Medium"
                    else:
                        return "🟢 Low"

                df_display["severity"] = df_display["flakiness_score"].apply(severity)

                # Format columns
                df_display["flakiness_score"] = df_display["flakiness_score"].apply(
                    lambda x: f"{x:.3f}"
                )

                # Select columns for display
                display_cols = {
                    "severity": "Severity",
                    "test": "Test Name",
                    "flakiness_score": "Score",
                    "total_runs": "Total Runs",
                    "failures": "Failures",
                    "recent_pattern": "Recent Pattern",
                }

                available_cols = [
                    col for col in display_cols.keys() if col in df_display.columns
                ]
                df_display = df_display[available_cols].rename(columns=display_cols)

                st.dataframe(
                    df_display, use_container_width=True, hide_index=True, height=400
                )

                # Pattern legend
                st.caption(
                    """
                **Pattern Legend:** P = Pass, F = Fail  
                *Recent Pattern shows the last 10 runs (left = oldest, right = newest)*
                """
                )

                st.divider()

                # Expandable details for each flaky test
                st.subheader("🔍 Detailed Analysis")

                for idx, row in df.head(5).iterrows():
                    test_name = row["test"]
                    score = row["flakiness_score"]
                    pattern = row.get("recent_pattern", "N/A")

                    with st.expander(f"**{test_name}** (Score: {score:.3f})"):
                        col_a, col_b = st.columns(2)

                        with col_a:
                            st.write(f"**Total Runs:** {row.get('total_runs', 0)}")
                            st.write(f"**Failures:** {row.get('failures', 0)}")
                            st.write(f"**Flakiness Score:** {score:.3f}")

                        with col_b:
                            st.write(f"**Recent Pattern:** `{pattern}`")
                            pass_rate = (
                                (row.get("total_runs", 1) - row.get("failures", 0))
                                / row.get("total_runs", 1)
                            ) * 100
                            st.write(f"**Pass Rate:** {pass_rate:.1f}%")

                        # Try to get recent failures
                        try:
                            history_response = requests.get(
                                f"{api_url}/api/v1/tests/history",
                                params={
                                    "project": project,
                                    "test_name": test_name,
                                    "limit": 10,
                                },
                                timeout=5,
                            )

                            if history_response.status_code == 200:
                                history = history_response.json().get("history", [])
                                if history:
                                    st.write("**Recent Executions:**")
                                    history_df = pd.DataFrame(history)
                                    if "timestamp" in history_df.columns:
                                        history_df["timestamp"] = pd.to_datetime(
                                            history_df["timestamp"], format="ISO8601"
                                        ).dt.strftime("%Y-%m-%d %H:%M")

                                    display_history = history_df[
                                        ["timestamp", "status", "duration_seconds"]
                                    ].rename(
                                        columns={
                                            "timestamp": "Time",
                                            "status": "Status",
                                            "duration_seconds": "Duration (s)",
                                        }
                                    )

                                    st.dataframe(display_history, hide_index=True)
                        except Exception:
                            pass

                        # Recommendations
                        st.write("**💡 Recommendations:**")
                        if score >= 0.5:
                            st.warning(
                                """
                            - 🚨 **CRITICAL**: This test is highly unstable
                            - Consider quarantining this test
                            - Investigate race conditions, timing issues, or external dependencies
                            - May need complete rewrite or removal
                            """
                            )
                        elif score >= 0.3:
                            st.info(
                                """
                            - ⚠️ **HIGH PRIORITY**: Investigate and fix soon
                            - Check for test data dependencies or shared state
                            - Review for async issues or improper waits
                            - Add retries as temporary mitigation
                            """
                            )
                        else:
                            st.success(
                                """
                            - ✅ **MODERATE**: Monitor this test
                            - Document any known intermittent issues
                            - Consider adding explicit waits or longer timeouts
                            """
                            )

            else:
                st.success("🎉 No flaky tests detected! Your test suite is stable.")
                st.balloons()

        else:
            st.error(f"Failed to fetch flaky tests: HTTP {response.status_code}")

    except requests.exceptions.Timeout:
        st.error("⏱️ Request timed out. The API may be slow or unreachable.")
    except requests.exceptions.ConnectionError:
        st.error(
            "🔌 Cannot connect to API. Please check the API URL and ensure the service is running."
        )
    except Exception as e:
        st.error(f"❌ Error loading flaky tests: {str(e)}")
