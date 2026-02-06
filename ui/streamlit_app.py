"""
Streamlit Web UI for AI Operations Assistant.
Interactive interface for submitting tasks and viewing results.
"""

import streamlit as st
import asyncio
import json
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from utils.logger import setup_logging
from agents.orchestrator import Orchestrator, OrchestratorState
from tools.registry import get_tool_registry


# Page config
st.set_page_config(
    page_title="AI Operations Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .status-success { color: #4CAF50; }
    .status-partial { color: #FF9800; }
    .status-failed { color: #F44336; }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "history" not in st.session_state:
        st.session_state.history = []
    if "current_result" not in st.session_state:
        st.session_state.current_result = None


def run_async(coro):
    """Run async coroutine in Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def execute_task(task: str):
    """Execute a task using the orchestrator."""
    settings = get_settings()
    setup_logging(settings.log_level, json_format=False)
    
    orchestrator = Orchestrator()
    result = await orchestrator.run(task)
    return result


def render_sidebar():
    """Render the sidebar with tools info and examples."""
    with st.sidebar:
        st.markdown("## 🔧 Available Tools")
        
        registry = get_tool_registry()
        for tool in registry.get_all():
            with st.expander(f"**{tool.name.upper()}**"):
                st.write(tool.description)
                st.write("**Actions:**")
                for action in tool.actions:
                    st.write(f"• `{action.name}`")
        
        st.markdown("---")
        st.markdown("## 💡 Example Tasks")
        
        examples = [
            "Get the weather in London",
            "Find top Python AI repositories",
            "Get tech news headlines",
            "Weather in Tokyo and JavaScript repos about React",
            "Search news about artificial intelligence"
        ]
        
        for example in examples:
            if st.button(f"📝 {example[:30]}...", key=example, use_container_width=True):
                st.session_state.task_input = example
                st.rerun()
        
        st.markdown("---")
        st.markdown("## 📊 Session Stats")
        st.metric("Tasks Executed", len(st.session_state.history))


def render_result(result):
    """Render the execution result."""
    if result.error:
        st.error(f"❌ Error: {result.error}")
        return
    
    if not result.output:
        st.warning("No output generated")
        return
    
    output = result.output
    
    # Status indicator
    status_icons = {"success": "✅", "partial": "⚠️", "failed": "❌"}
    status_colors = {"success": "green", "partial": "orange", "failed": "red"}
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Status", f"{status_icons.get(output.status, '❓')} {output.status.upper()}")
    with col2:
        st.metric("Steps", f"{output.execution_details.get('steps_succeeded', 0)}/{output.execution_details.get('steps_total', 0)}")
    with col3:
        st.metric("Time", f"{output.execution_details.get('total_time_ms', 0):.0f}ms")
    
    st.markdown("---")
    
    # Summary
    st.markdown("### 📋 Summary")
    st.info(output.summary)
    
    # Data sections
    if output.data:
        st.markdown("### 📊 Results")
        
        for key, value in output.data.items():
            with st.expander(f"**{key.replace('_', ' ').title()}**", expanded=True):
                if isinstance(value, dict):
                    # Weather data
                    if "temperature" in value or "city" in value:
                        cols = st.columns(4)
                        with cols[0]:
                            st.metric("City", f"{value.get('city', 'N/A')}, {value.get('country', '')}")
                        with cols[1]:
                            st.metric("Temperature", f"{value.get('temperature', 'N/A')}{value.get('unit', '°C')}")
                        with cols[2]:
                            st.metric("Humidity", f"{value.get('humidity', 'N/A')}%")
                        with cols[3]:
                            st.metric("Condition", value.get('description', 'N/A'))
                    
                    # Repository data
                    elif "repositories" in value:
                        repos = value.get("repositories", [])
                        if repos:
                            import pandas as pd
                            df = pd.DataFrame([
                                {
                                    "Name": r.get("name", ""),
                                    "⭐ Stars": r.get("stars", 0),
                                    "Language": r.get("language", ""),
                                    "Description": (r.get("description", "") or "")[:60]
                                }
                                for r in repos
                            ])
                            st.dataframe(df, use_container_width=True)
                    
                    # News data
                    elif "articles" in value:
                        articles = value.get("articles", [])
                        for article in articles:
                            st.markdown(f"**{article.get('source', 'Unknown')}**: {article.get('title', 'No title')}")
                            if article.get('url'):
                                st.markdown(f"[Read more]({article.get('url')})")
                            st.markdown("---")
                    
                    else:
                        st.json(value)
                else:
                    st.write(value)
    
    # Execution plan
    if result.plan:
        with st.expander("🗺️ Execution Plan"):
            st.markdown(f"**Understanding:** {result.plan.task_understanding}")
            st.markdown("**Steps:**")
            for step in result.plan.steps:
                st.markdown(
                    f"{step.step_number}. `{step.tool}.{step.action}` - {step.reasoning}"
                )
    
    # Errors
    if output.errors:
        st.markdown("### ⚠️ Errors")
        for error in output.errors:
            st.warning(error)


def main():
    """Main application."""
    init_session_state()
    
    # Header
    st.markdown('<p class="main-header">🤖 AI Operations Assistant</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Execute natural language tasks using AI agents</p>', unsafe_allow_html=True)
    
    # Render sidebar
    render_sidebar()
    
    # Main content
    col1, col2 = st.columns([4, 1])
    
    with col1:
        task_input = st.text_area(
            "Enter your task",
            value=st.session_state.get("task_input", ""),
            placeholder="e.g., Get the weather in San Francisco and find popular Python machine learning repositories",
            height=100,
            key="task_area"
        )
    
    with col2:
        st.write("")  # Spacer
        st.write("")
        execute_btn = st.button("🚀 Execute", type="primary", use_container_width=True)
    
    # Execute task
    if execute_btn and task_input:
        with st.spinner("🧠 Planning and executing..."):
            try:
                result = run_async(execute_task(task_input))
                st.session_state.current_result = result
                st.session_state.history.append({
                    "task": task_input,
                    "status": result.output.status if result.output else "error",
                    "time": datetime.now().isoformat()
                })
            except Exception as e:
                st.error(f"Execution failed: {e}")
    
    # Show result
    if st.session_state.current_result:
        st.markdown("---")
        render_result(st.session_state.current_result)
    
    # History
    if st.session_state.history:
        st.markdown("---")
        st.markdown("### 📜 Task History")
        for i, item in enumerate(reversed(st.session_state.history[-5:])):
            status_icon = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(item["status"], "❓")
            st.text(f"{status_icon} {item['task'][:50]}...")


if __name__ == "__main__":
    main()
