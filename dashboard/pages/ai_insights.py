"""
AI Insights Page

Provides AI-powered analysis and recommendations for test health.
"""

import streamlit as st
import requests
import os
from datetime import datetime


def render(api_url: str, project: str, days: int):
    """Render the AI insights page."""

    st.header("🤖 AI-Powered Insights")
    st.markdown(
        """
    Leverage AI to generate intelligent summaries, root cause analysis, and actionable recommendations
    for improving your test suite health.
    """
    )

    # Configuration
    with st.expander("⚙️ OpenAI Configuration", expanded=False):
        st.markdown(
            """
        To enable AI insights, you need to provide an OpenAI API key.
        
        **How to get started:**
        1. Sign up for an OpenAI account at https://platform.openai.com/
        2. Create an API key from your account dashboard
        3. Enter your API key below (it will be stored in your session only)
        """
        )

        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Your OpenAI API key (stored in session only)",
            value=os.getenv("OPENAI_API_KEY", ""),
        )

        st.session_state.model = st.selectbox(
            "Model",
            options=["gpt-4", "gpt-4-turbo-preview", "gpt-3.5-turbo"],
            index=0,
            help="GPT model to use for analysis",
        )

        if api_key:
            st.success("✅ API key configured")
        else:
            st.warning("⚠️ No API key provided. AI insights will not be available.")

    st.divider()

    if not api_key:
        st.info(
            """
        📝 **Note:** AI insights require an OpenAI API key. 
        Please provide one in the configuration section above.
        """
        )
        return

    # Analysis options
    st.subheader("🎯 Analysis Type")

    analysis_type = st.radio(
        "Select analysis to generate:",
        options=[
            "🔍 Comprehensive Test Health Summary",
            "🔄 Flaky Test Root Cause Analysis",
            "🐌 Slow Test Optimization Recommendations",
            "❌ Failure Pattern Analysis",
            "📊 Custom Query",
        ],
        index=0,
    )

    st.divider()

    # Generate button
    if st.button("🚀 Generate AI Analysis", type="primary", use_container_width=True):
        with st.spinner("🤖 AI is analyzing your test data..."):
            try:
                # Fetch relevant data based on analysis type
                if "Comprehensive" in analysis_type:
                    data = fetch_comprehensive_data(api_url, project, days)
                    prompt = generate_comprehensive_prompt(data, project, days)

                elif "Flaky" in analysis_type:
                    data = fetch_flaky_data(api_url, project, days)
                    prompt = generate_flaky_prompt(data, project)

                elif "Slow" in analysis_type:
                    data = fetch_slow_data(api_url, project, days)
                    prompt = generate_slow_prompt(data, project)

                elif "Failure" in analysis_type:
                    data = fetch_failure_data(api_url, project, days)
                    prompt = generate_failure_prompt(data, project, days)

                else:  # Custom Query
                    custom_query = st.text_area(
                        "Enter your question:",
                        placeholder="e.g., What are the main causes of test instability in our suite?",
                    )
                    if not custom_query:
                        st.warning("Please enter a question for the AI to answer.")
                        return

                    data = fetch_comprehensive_data(api_url, project, days)
                    prompt = generate_custom_prompt(data, custom_query, project)

                # Call OpenAI API (simulated - real implementation would use openai library)
                # For this demo, we'll show a mock response
                st.success("✅ Analysis complete!")

                # Display results
                st.subheader("📄 AI Analysis Results")

                # This is a placeholder - real implementation would call OpenAI
                st.markdown(
                    f"""
                ### Analysis for Project: `{project}`
                **Period:** Last {days} days  
                **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                
                ---
                
                #### 🎯 Key Findings
                
                Based on the test data analysis, here are the most critical insights:
                
                1. **Test Stability:** {generate_stability_insight(data)}
                2. **Performance:** {generate_performance_insight(data)}
                3. **Failure Patterns:** {generate_failure_insight(data)}
                
                #### 💡 Recommendations
                
                {generate_recommendations(data, analysis_type)}
                
                #### 📊 Priority Actions
                
                {generate_priority_actions(data)}
                
                ---
                
                *Note: This is a demonstration output. In production, this would be generated by GPT-4 
                using the actual test data and would provide much more detailed, context-aware insights.*
                """
                )

                # Show the prompt that would be sent to OpenAI
                with st.expander("🔍 View Generated Prompt"):
                    st.code(prompt, language="text")

                # Download option
                col1, col2 = st.columns([3, 1])
                with col2:
                    st.download_button(
                        label="📥 Export Analysis",
                        data=prompt,  # In production, would be the AI response
                        file_name=f"test_analysis_{project}_{datetime.now().strftime('%Y%m%d')}.md",
                        mime="text/markdown",
                    )

            except Exception as e:
                st.error(f"❌ Error generating AI analysis: {str(e)}")

    st.divider()

    # AI Tips Section
    st.subheader("💡 AI Analysis Tips")

    with st.expander("📚 How to get the most from AI insights"):
        st.markdown(
            """
        ### Best Practices:
        
        1. **Provide Context**: The more test data available, the better the AI insights
        2. **Regular Analysis**: Run analyses weekly to track improvements
        3. **Specific Questions**: For custom queries, be specific about what you want to know
        4. **Action-Oriented**: Focus on actionable recommendations
        5. **Iterate**: Use AI suggestions as a starting point for deeper investigation
        
        ### What AI Can Help With:
        
        - Identifying patterns humans might miss
        - Suggesting root causes based on error patterns
        - Prioritizing which tests to fix first
        - Recommending optimization strategies
        - Generating test improvement roadmaps
        
        ### Limitations:
        
        - AI doesn't have access to your codebase
        - Suggestions need to be validated by your team
        - Domain knowledge is still crucial
        - AI is a tool to augment, not replace, human judgment
        """
        )


def fetch_comprehensive_data(api_url: str, project: str, days: int) -> dict:
    """Fetch all relevant data for comprehensive analysis."""
    data = {}

    try:
        # Health score
        response = requests.get(
            f"{api_url}/api/v1/health-score/{project}",
            params={"lookback_days": days},
            timeout=5,
        )
        if response.status_code == 200:
            data["health"] = response.json()

        # Flaky tests
        response = requests.get(
            f"{api_url}/api/v1/tests/flaky",
            params={"project": project, "lookback_days": days},
            timeout=5,
        )
        if response.status_code == 200:
            data["flaky"] = response.json()

        # Slow tests
        response = requests.get(
            f"{api_url}/api/v1/tests/slow",
            params={"project": project, "threshold_seconds": 5.0},
            timeout=5,
        )
        if response.status_code == 200:
            data["slow"] = response.json()

        # Failure clusters
        response = requests.get(
            f"{api_url}/api/v1/failures/clusters",
            params={"project": project, "lookback_days": days},
            timeout=5,
        )
        if response.status_code == 200:
            data["failures"] = response.json()

    except Exception as e:
        st.warning(f"Some data could not be fetched: {str(e)}")

    return data


def fetch_flaky_data(api_url: str, project: str, days: int) -> dict:
    """Fetch flaky test data."""
    try:
        response = requests.get(
            f"{api_url}/api/v1/tests/flaky",
            params={"project": project, "lookback_days": days},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {}


def fetch_slow_data(api_url: str, project: str, days: int) -> dict:
    """Fetch slow test data."""
    try:
        response = requests.get(
            f"{api_url}/api/v1/tests/slow",
            params={"project": project, "threshold_seconds": 5.0},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {}


def fetch_failure_data(api_url: str, project: str, days: int) -> dict:
    """Fetch failure cluster data."""
    try:
        response = requests.get(
            f"{api_url}/api/v1/failures/clusters",
            params={"project": project, "lookback_days": days},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {}


def generate_comprehensive_prompt(data: dict, project: str, days: int) -> str:
    """Generate prompt for comprehensive analysis."""
    return f"""
Analyze the test health data for project '{project}' over the last {days} days:

HEALTH SCORE: {data.get('health', {}).get('health_score', 'N/A')}
FLAKY TESTS: {len(data.get('flaky', {}).get('flaky_tests', []))} detected
SLOW TESTS: {len(data.get('slow', {}).get('slow_tests', []))} detected
FAILURE CLUSTERS: {len(data.get('failures', {}).get('clusters', []))} detected

Provide:
1. Executive summary of test health
2. Top 3 critical issues
3. Root cause hypotheses
4. Prioritized action plan
5. Expected impact of recommended changes
"""


def generate_flaky_prompt(data: dict, project: str) -> str:
    """Generate prompt for flaky test analysis."""
    flaky_count = len(data.get("flaky_tests", []))
    return f"""
Analyze {flaky_count} flaky tests in project '{project}'.

Provide:
1. Common patterns in flaky behavior
2. Most likely root causes
3. Step-by-step remediation plan
4. Prevention strategies
"""


def generate_slow_prompt(data: dict, project: str) -> str:
    """Generate prompt for slow test analysis."""
    slow_count = len(data.get("slow_tests", []))
    return f"""
Analyze {slow_count} slow tests in project '{project}'.

Provide:
1. Performance bottleneck analysis
2. Optimization opportunities
3. Quick wins vs long-term improvements
4. Expected time savings
"""


def generate_failure_prompt(data: dict, project: str, days: int) -> str:
    """Generate prompt for failure analysis."""
    cluster_count = len(data.get("clusters", []))
    return f"""
Analyze {cluster_count} failure clusters from the last {days} days in project '{project}'.

Provide:
1. Root cause analysis for each major cluster
2. Systemic vs isolated issues
3. Fix prioritization strategy
4. Preventive measures
"""


def generate_custom_prompt(data: dict, query: str, project: str) -> str:
    """Generate prompt for custom query."""
    return f"""
Project: {project}

Test Health Data Summary:
- Health Score: {data.get('health', {}).get('health_score', 'N/A')}
- Flaky Tests: {len(data.get('flaky', {}).get('flaky_tests', []))}
- Slow Tests: {len(data.get('slow', {}).get('slow_tests', []))}
- Failure Clusters: {len(data.get('failures', {}).get('clusters', []))}

User Question: {query}

Provide a detailed, actionable answer based on the test data.
"""


def generate_stability_insight(data: dict) -> str:
    """Generate stability insight."""
    flaky_count = len(data.get("flaky", {}).get("flaky_tests", []))
    if flaky_count == 0:
        return "Excellent stability with no flaky tests detected ✅"
    elif flaky_count < 5:
        return f"Generally stable, but {flaky_count} flaky tests need attention ⚠️"
    else:
        return f"Stability concerns with {flaky_count} flaky tests identified 🔴"


def generate_performance_insight(data: dict) -> str:
    """Generate performance insight."""
    slow_count = len(data.get("slow", {}).get("slow_tests", []))
    if slow_count == 0:
        return "Good performance profile across all tests ✅"
    elif slow_count < 10:
        return f"Minor performance issues with {slow_count} slow tests ⚠️"
    else:
        return f"Significant performance concerns with {slow_count} slow tests 🔴"


def generate_failure_insight(data: dict) -> str:
    """Generate failure insight."""
    cluster_count = len(data.get("failures", {}).get("clusters", []))
    if cluster_count == 0:
        return "No systematic failure patterns detected ✅"
    elif cluster_count < 3:
        return f"{cluster_count} failure pattern(s) identified for investigation ⚠️"
    else:
        return f"Multiple systematic issues with {cluster_count} failure clusters 🔴"


def generate_recommendations(data: dict, analysis_type: str) -> str:
    """Generate recommendations based on data."""
    recommendations = []

    flaky_count = len(data.get("flaky", {}).get("flaky_tests", []))
    slow_count = len(data.get("slow", {}).get("slow_tests", []))
    cluster_count = len(data.get("failures", {}).get("clusters", []))

    if flaky_count > 0:
        recommendations.append(
            f"1. **Address Flaky Tests**: Prioritize fixing {min(flaky_count, 5)} most critical flaky tests"
        )

    if slow_count > 0:
        recommendations.append(
            f"2. **Optimize Performance**: Target top {min(slow_count, 10)} slow tests for optimization"
        )

    if cluster_count > 0:
        recommendations.append(
            f"3. **Fix Systemic Issues**: Investigate {cluster_count} failure pattern(s) for root causes"
        )

    if not recommendations:
        recommendations.append(
            "1. **Maintain Excellence**: Continue current testing practices"
        )
        recommendations.append(
            "2. **Add Coverage**: Consider expanding test coverage for edge cases"
        )

    return "\n".join(recommendations)


def generate_priority_actions(data: dict) -> str:
    """Generate priority actions."""
    actions = []

    health_score = data.get("health", {}).get("health_score", 100)

    if health_score < 50:
        actions.append("🚨 **URGENT**: Schedule test health improvement sprint")
    elif health_score < 75:
        actions.append(
            "⚠️ **HIGH**: Allocate 20% of sprint capacity to test improvements"
        )
    else:
        actions.append("✅ **MAINTAIN**: Continue regular test maintenance")

    actions.append("📊 **TRACK**: Monitor test health metrics weekly")
    actions.append("👥 **REVIEW**: Discuss findings in next team retrospective")

    return "\n".join(actions)
