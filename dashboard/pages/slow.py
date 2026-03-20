"""
Slow Tests Page

Identifies tests that take too long to execute.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def render(api_url: str, project: str, days: int):
    """Render the slow tests page."""
    
    st.header("🐌 Slow Test Detection")
    st.markdown("""
    Slow tests increase feedback time and reduce developer productivity. 
    Identify and optimize tests that take too long to execute.
    """)
    
    # Configuration
    col1, col2, col3 = st.columns(3)
    
    with col1:
        threshold = st.slider(
            "Duration Threshold (seconds)",
            min_value=0.5,
            max_value=30.0,
            value=5.0,
            step=0.5,
            help="Tests slower than this threshold will be flagged"
        )
    
    with col2:
        limit = st.number_input(
            "Max Results",
            min_value=10,
            max_value=200,
            value=50,
            help="Maximum number of slow tests to display"
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort By",
            options=["Average Duration", "Max Duration", "Run Count"],
            index=0
        )
    
    st.divider()
    
    # Fetch slow tests
    try:
        response = requests.get(
            f"{api_url}/api/v1/tests/slow",
            params={
                "project": project,
                "threshold_seconds": threshold,
                "limit": limit
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            slow_tests = data.get('slow_tests', [])
            
            if slow_tests:
                st.warning(f"Found {len(slow_tests)} slow test(s) exceeding {threshold}s threshold")
                
                # Convert to DataFrame
                df = pd.DataFrame(slow_tests)
                
                # Sort
                if sort_by == "Average Duration":
                    df = df.sort_values('avg_duration', ascending=False)
                elif sort_by == "Max Duration":
                    df = df.sort_values('max_duration', ascending=False)
                else:
                    df = df.sort_values('run_count', ascending=False)
                
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Slow Tests", len(df))
                
                with col2:
                    total_time = df['avg_duration'].sum()
                    st.metric("Total Avg Time", f"{total_time:.1f}s")
                
                with col3:
                    slowest = df['max_duration'].max()
                    st.metric("Slowest Test", f"{slowest:.1f}s")
                
                with col4:
                    median_duration = df['avg_duration'].median()
                    st.metric("Median Duration", f"{median_duration:.1f}s")
                
                st.divider()
                
                # Visualization: Top 15 Slow Tests
                st.subheader("📊 Top 15 Slowest Tests")
                
                df_top = df.head(15).copy()
                
                # Shorten test names
                df_top['short_name'] = df_top['test'].apply(
                    lambda x: x.split('::')[-1] if '::' in x else x[-50:]
                )
                
                fig = go.Figure()
                
                # Average duration bars
                fig.add_trace(go.Bar(
                    y=df_top['short_name'],
                    x=df_top['avg_duration'],
                    name='Avg Duration',
                    orientation='h',
                    marker=dict(color='#ffc107'),
                    text=df_top['avg_duration'].apply(lambda x: f"{x:.2f}s"),
                    textposition='outside'
                ))
                
                # Max duration markers
                fig.add_trace(go.Scatter(
                    y=df_top['short_name'],
                    x=df_top['max_duration'],
                    name='Max Duration',
                    mode='markers',
                    marker=dict(
                        size=10,
                        color='#dc3545',
                        symbol='diamond'
                    )
                ))
                
                fig.update_layout(
                    title='Test Duration (Average vs Max)',
                    xaxis_title='Duration (seconds)',
                    yaxis_title='Test',
                    height=500,
                    showlegend=True,
                    yaxis={'categoryorder': 'total ascending'}
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.divider()
                
                # Duration Distribution
                st.subheader("📈 Duration Distribution")
                
                fig_hist = px.histogram(
                    df,
                    x='avg_duration',
                    nbins=30,
                    title='Distribution of Average Test Durations',
                    labels={'avg_duration': 'Average Duration (s)', 'count': 'Number of Tests'},
                    color_discrete_sequence=['#17a2b8']
                )
                
                fig_hist.add_vline(
                    x=threshold,
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"Threshold: {threshold}s"
                )
                
                st.plotly_chart(fig_hist, use_container_width=True)
                
                st.divider()
                
                # Detailed Table
                st.subheader("📋 Detailed Slow Test List")
                
                # Categorize by severity
                def categorize_speed(duration):
                    if duration >= threshold * 5:
                        return "🔴 Critical"
                    elif duration >= threshold * 3:
                        return "🟠 Very Slow"
                    elif duration >= threshold * 2:
                        return "🟡 Slow"
                    else:
                        return "🟢 Above Threshold"
                
                df_display = df.copy()
                df_display['category'] = df_display['avg_duration'].apply(categorize_speed)
                
                # Format durations
                df_display['avg_duration'] = df_display['avg_duration'].apply(lambda x: f"{x:.2f}s")
                df_display['max_duration'] = df_display['max_duration'].apply(lambda x: f"{x:.2f}s")
                
                # Select columns for display
                display_cols = {
                    'category': 'Category',
                    'test': 'Test Name',
                    'avg_duration': 'Avg Duration',
                    'max_duration': 'Max Duration',
                    'run_count': 'Run Count'
                }
                
                available_cols = [col for col in display_cols.keys() if col in df_display.columns]
                df_display = df_display[available_cols].rename(columns=display_cols)
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )
                
                st.divider()
                
                # Time savings opportunity
                st.subheader("⏱️ Optimization Opportunity")
                
                st.markdown("""
                Calculate potential time savings if top slow tests were optimized:
                """)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    optimize_count = st.number_input(
                        "Number of tests to optimize",
                        min_value=1,
                        max_value=len(df),
                        value=min(10, len(df)),
                        help="Select how many of the slowest tests to include in savings calculation"
                    )
                
                with col2:
                    improvement = st.slider(
                        "Expected improvement (%)",
                        min_value=10,
                        max_value=90,
                        value=50,
                        step=5,
                        help="Expected percentage reduction in test duration"
                    )
                
                # Calculate savings
                top_slow = df.head(optimize_count)
                current_time = top_slow['avg_duration'].sum()
                runs_per_day = 10  # Assume 10 runs per day
                
                time_saved_per_run = current_time * (improvement / 100)
                time_saved_per_day = time_saved_per_run * runs_per_day
                time_saved_per_month = time_saved_per_day * 22  # Working days
                
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    st.metric(
                        "Savings per Run",
                        f"{time_saved_per_run:.1f}s",
                        help="Time saved in each test run"
                    )
                
                with col_b:
                    st.metric(
                        "Savings per Day",
                        f"{time_saved_per_day / 60:.1f} min",
                        help=f"Based on {runs_per_day} runs/day"
                    )
                
                with col_c:
                    st.metric(
                        "Savings per Month",
                        f"{time_saved_per_month / 3600:.1f} hrs",
                        help="Based on 22 working days"
                    )
                
                st.info(f"""
                💡 **Insight:** Optimizing the top {optimize_count} slowest tests by {improvement}% 
                could save approximately **{time_saved_per_month / 3600:.1f} hours** of CI/CD time per month!
                """)
                
                st.divider()
                
                # Optimization recommendations
                st.subheader("💡 Optimization Recommendations")
                
                with st.expander("🎯 General Strategies"):
                    st.markdown("""
                    ### Common Causes of Slow Tests:
                    
                    1. **Database Operations**
                       - Use in-memory databases for tests
                       - Mock external database calls
                       - Batch database operations
                    
                    2. **External API Calls**
                       - Mock HTTP requests
                       - Use fake/stub services
                       - Consider contract testing
                    
                    3. **File I/O**
                       - Use temporary in-memory file systems
                       - Mock file operations where possible
                       - Clean up resources properly
                    
                    4. **Long Waits/Sleeps**
                       - Replace fixed sleeps with condition polling
                       - Use faster polling intervals in tests
                       - Mock time-dependent operations
                    
                    5. **Heavy Computations**
                       - Use smaller datasets in tests
                       - Pre-compute and cache results
                       - Consider unit tests vs integration tests
                    
                    6. **Test Setup/Teardown**
                       - Share fixtures across tests (use sparingly)
                       - Optimize test data generation
                       - Parallelize independent setup steps
                    """)
                
                # Show specific recommendations for top slow tests
                for idx, row in df.head(3).iterrows():
                    test_name = row['test']
                    avg_dur = row['avg_duration']
                    max_dur = row['max_duration']
                    
                    with st.expander(f"**{test_name}** ({avg_dur:.2f}s avg)"):
                        st.write(f"**Average Duration:** {avg_dur:.2f}s")
                        st.write(f"**Maximum Duration:** {max_dur:.2f}s")
                        st.write(f"**Run Count:** {row.get('run_count', 0)}")
                        
                        st.write("**Suggested Actions:**")
                        if avg_dur >= threshold * 5:
                            st.error("""
                            - 🚨 **CRITICAL**: This test is extremely slow
                            - Consider splitting into multiple smaller tests
                            - Profile the test to identify bottlenecks
                            - May need architectural changes or mocking
                            """)
                        elif avg_dur >= threshold * 3:
                            st.warning("""
                            - ⚠️ **HIGH PRIORITY**: Significant optimization needed
                            - Review for unnecessary waits or polling
                            - Check for redundant setup/teardown operations
                            - Consider parallelization opportunities
                            """)
                        else:
                            st.info("""
                            - ℹ️ **MODERATE**: Room for improvement
                            - Review test scope - could it be more focused?
                            - Look for easy wins (mocking, caching)
                            - Monitor for performance regressions
                            """)
            
            else:
                st.success(f"🎉 No tests slower than {threshold}s threshold!")
                st.balloons()
        
        else:
            st.error(f"Failed to fetch slow tests: HTTP {response.status_code}")
    
    except requests.exceptions.Timeout:
        st.error("⏱️ Request timed out. The API may be slow or unreachable.")
    except requests.exceptions.ConnectionError:
        st.error("🔌 Cannot connect to API. Please check the API URL and ensure the service is running.")
    except Exception as e:
        st.error(f"❌ Error loading slow tests: {str(e)}")
