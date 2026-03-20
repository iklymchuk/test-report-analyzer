"""
Overview Page - Test Health Dashboard

Displays high-level metrics, trends, and test run history.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta


def render(api_url: str, project: str, days: int):
    """Render the overview page."""
    
    # Health Score Section
    st.header("🎯 Test Health Score")
    
    try:
        health_response = requests.get(
            f"{api_url}/api/v1/health-score/{project}",
            params={"lookback_days": days},
            timeout=5
        )
        
        if health_response.status_code == 200:
            health_data = health_response.json()
            score = health_data.get('health_score', 0)
            
            # Display health score with color coding
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                # Determine color based on score
                if score >= 80:
                    color = "🟢"
                    status = "Excellent"
                elif score >= 60:
                    color = "🟡"
                    status = "Good"
                elif score >= 40:
                    color = "🟠"
                    status = "Fair"
                else:
                    color = "🔴"
                    status = "Poor"
                
                st.metric(
                    "Health Score",
                    f"{score:.1f}/100",
                    delta=None,
                    help="Overall test suite health (0-100)"
                )
                st.markdown(f"{color} **{status}**")
            
            with col2:
                st.metric(
                    "Pass Rate",
                    f"{health_data.get('pass_rate', 0):.1f}%",
                    help="Percentage of tests passing"
                )
            
            with col3:
                st.metric(
                    "Stability",
                    f"{health_data.get('stability_score', 0):.1f}%",
                    help="Test consistency over time"
                )
            
            with col4:
                st.metric(
                    "Performance",
                    f"{health_data.get('performance_score', 0):.1f}%",
                    help="Test execution speed relative to baseline"
                )
            
            # Show contributing factors
            with st.expander("📊 Score Breakdown"):
                factors = health_data.get('factors', {})
                st.write("**Contributing Factors:**")
                for factor, value in factors.items():
                    st.write(f"- {factor.replace('_', ' ').title()}: {value:.1f}")
        
        else:
            st.warning("Health score data not available")
    
    except Exception as e:
        st.error(f"Failed to load health score: {str(e)}")
    
    st.divider()
    
    # Latest Run Statistics
    st.header("📊 Latest Test Run")
    
    try:
        runs_response = requests.get(
            f"{api_url}/api/v1/runs",
            params={"project": project, "limit": 1},
            timeout=5
        )
        
        if runs_response.status_code == 200 and runs_response.json():
            latest_run = runs_response.json()[0]
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Total Tests", latest_run.get('total_tests', 0))
            
            with col2:
                passed = latest_run.get('passed', 0)
                st.metric("✅ Passed", passed)
            
            with col3:
                failed = latest_run.get('failed', 0)
                delta_color = "inverse" if failed > 0 else "normal"
                st.metric("❌ Failed", failed)
            
            with col4:
                skipped = latest_run.get('skipped', 0)
                st.metric("⏭️ Skipped", skipped)
            
            with col5:
                duration = latest_run.get('duration_seconds', 0)
                st.metric("⏱️ Duration", f"{duration:.1f}s")
            
            # Show run details
            with st.expander("🔍 Run Details"):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**Branch:** `{latest_run.get('branch', 'N/A')}`")
                    st.write(f"**Commit:** `{latest_run.get('commit_sha', 'N/A')[:8]}`")
                with col_b:
                    timestamp = latest_run.get('timestamp', '')
                    if timestamp:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        st.write(f"**Time:** {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    st.write(f"**Status:** `{latest_run.get('status', 'unknown')}`")
        
        else:
            st.info("No test runs found for this project")
    
    except Exception as e:
        st.error(f"Failed to load latest run: {str(e)}")
    
    st.divider()
    
    # Failure Trend Chart
    st.header("📉 Failure Trend")
    
    try:
        trends_response = requests.get(
            f"{api_url}/api/v1/trends/{project}",
            params={"days": days},
            timeout=5
        )
        
        if trends_response.status_code == 200:
            trends_data = trends_response.json()
            data_points = trends_data.get('data_points', [])
            
            if data_points:
                df = pd.DataFrame(data_points)
                df['date'] = pd.to_datetime(df['date'], format='ISO8601')
                
                # Create dual-axis chart
                fig = go.Figure()
                
                # Failure rate line
                fig.add_trace(go.Scatter(
                    x=df['date'],
                    y=df['failure_rate'],
                    name='Failure Rate',
                    line=dict(color='#dc3545', width=2),
                    mode='lines+markers',
                    yaxis='y'
                ))
                
                # Total tests bar
                fig.add_trace(go.Bar(
                    x=df['date'],
                    y=df['total_tests'],
                    name='Total Tests',
                    marker=dict(color='#6c757d', opacity=0.3),
                    yaxis='y2'
                ))
                
                fig.update_layout(
                    title='Test Failure Rate and Volume Over Time',
                    xaxis=dict(title='Date'),
                    yaxis=dict(
                        title='Failure Rate (%)',
                        side='left',
                        titlefont=dict(color='#dc3545'),
                        tickfont=dict(color='#dc3545')
                    ),
                    yaxis2=dict(
                        title='Total Tests',
                        side='right',
                        overlaying='y',
                        titlefont=dict(color='#6c757d'),
                        tickfont=dict(color='#6c757d')
                    ),
                    hovermode='x unified',
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Show trend statistics
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    avg_failure_rate = df['failure_rate'].mean()
                    st.metric("Avg Failure Rate", f"{avg_failure_rate:.1f}%")
                
                with col2:
                    trend_direction = trends_data.get('trend_direction', 'stable')
                    trend_emoji = {
                        'improving': '📈',
                        'degrading': '📉',
                        'stable': '➡️'
                    }.get(trend_direction, '➡️')
                    st.metric("Trend", f"{trend_emoji} {trend_direction.title()}")
                
                with col3:
                    total_runs = len(data_points)
                    st.metric("Total Runs", total_runs)
            
            else:
                st.info("No trend data available for the selected time period")
        
        else:
            st.warning("Unable to load trend data")
    
    except Exception as e:
        st.error(f"Failed to load trends: {str(e)}")
    
    st.divider()
    
    # Recent Test Runs Table
    st.header("📋 Recent Test Runs")
    
    try:
        runs_response = requests.get(
            f"{api_url}/api/v1/runs",
            params={"project": project, "limit": 20},
            timeout=5
        )
        
        if runs_response.status_code == 200:
            runs = runs_response.json()
            
            if runs:
                # Prepare dataframe
                df_runs = pd.DataFrame(runs)
                
                # Format timestamp
                if 'timestamp' in df_runs.columns:
                    df_runs['timestamp'] = pd.to_datetime(df_runs['timestamp'], format='ISO8601').dt.strftime('%Y-%m-%d %H:%M')
                
                # Select and rename columns
                display_columns = {
                    'timestamp': 'Time',
                    'branch': 'Branch',
                    'total_tests': 'Total',
                    'passed': 'Passed',
                    'failed': 'Failed',
                    'skipped': 'Skipped',
                    'duration_seconds': 'Duration (s)',
                    'status': 'Status'
                }
                
                available_columns = [col for col in display_columns.keys() if col in df_runs.columns]
                df_display = df_runs[available_columns].rename(columns=display_columns)
                
                # Display with styling
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )
            else:
                st.info("No test runs found")
        
        else:
            st.warning("Unable to load test runs")
    
    except Exception as e:
        st.error(f"Failed to load test runs: {str(e)}")
