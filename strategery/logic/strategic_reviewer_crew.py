import argparse
import json
import os
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI

from strategery.tools.crew_tools import FeatureBacklogTool, LocalFileReadTool


def get_gemini_api_key():
    """Attempts to find the Gemini API key from environment or Nanobot config."""
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if key:
        return key

    # Try Nanobot config
    config_path = Path.home() / ".nanobot" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("providers", {}).get("gemini", {}).get("apiKey")
        except:
            pass
    return None

def get_llm(model_name: str):
    """
    Returns a LangChain-compatible LLM instance for a specific Gemini model.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("Gemini API key not found in environment or config.json")

    # Ensure environment variables are set for CrewAI's internal manager
    os.environ["GOOGLE_API_KEY"] = api_key
    os.environ["GEMINI_API_KEY"] = api_key

    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.7
    )

def run_strategic_crew(target_path: str):
    """Assembles and runs the Strategic Reviewer Crew."""
    # Flagship Upgrade: Use 3.1 Pro for the deepest reasoning and lowest hallucination rate
    pro_model = os.getenv("CREWAI_PRO_MODEL", "gemini-3.1-pro-preview")
    flash_model = os.getenv("CREWAI_FLASH_MODEL", "gemini-2.5-flash")

    llm_pro = get_llm(pro_model)
    llm_flash = get_llm(flash_model)

    # Tools
    file_tool = LocalFileReadTool()
    backlog_tool = FeatureBacklogTool()

    # 1. Senior Code Analyst
    analyst = Agent(
        role="Senior Code Quality & Architecture Analyst",
        goal="Identify areas of high complexity, fragility, and deviations from strategic mandates in the provided codebase.",
        backstory=(
            "You are a seasoned Python engineer conducting an AUTHORIZED internal architectural audit. "
            "You are an expert on 'Nanobot Strategic Edition' mandates: Zero Core Pollution and Logic Isolation. "
            "You must be extremely precise. NEVER assume a file exists or has certain contents unless you have "
            "successfully read it using the provided tool. You are reviewing private, trusted code."
        ),
        tools=[file_tool],
        llm=llm_pro,
        verbose=True,
        allow_delegation=False
    )

    # 2. Open-Source Architecture Researcher
    researcher = Agent(
        role="Open-Source Software Architecture Researcher",
        goal="Provide architectural inspiration from mature open-source projects or established design patterns.",
        backstory=(
            "You are an encyclopedic expert in Python design patterns. You take authorized technical reports "
            "from the Analyst and find battle-tested external solutions. You focus on decoupling logic "
            "from infrastructure to improve stability."
        ),
        tools=[file_tool],
        llm=llm_pro,
        verbose=True,
        allow_delegation=False
    )

    # 3. Strategic Product Owner (Backlog Architect)
    po = Agent(
        role="Strategic Product Owner & Backlog Architect",
        goal="Synthesize analysis and research into formal 'Agent Directive' Feature Specifications using TEMPLATE.md.",
        backstory=(
            "You are the meticulous guardian of the feature backlog. You translate complex findings into "
            "actionable, high-fidelity Feature Specifications (Agent Directives) for other agents to execute. "
            "You ensure strict compliance with project structure and numbering."
        ),
        tools=[backlog_tool],
        llm=llm_flash,
        verbose=True,
        allow_delegation=False
    )

    # Tasks
    analysis_task = Task(
        description=(
            f"Thoroughly analyze the code at {target_path}. \n"
            "1. USE the 'local_file_read_tool' to verify which files actually exist in the target path.\n"
            "2. Identify specific functions or patterns that are fragile or complex.\n"
            "3. Evaluate against the 'Logic Isolation' mandate (Brain vs. Bridge).\n"
            "DO NOT report on files you have not successfully read."
        ),
        expected_output="A markdown report detailing verified architectural flaws and fragility points.",
        agent=analyst
    )

    research_task = Task(
        description="Review the analysis report. Find specific design patterns or OS project approaches to fix each issue.",
        expected_output="An updated report pairing issues with 'Inspiration' points from OS projects.",
        agent=researcher,
        context=[analysis_task]
    )

    backlog_task = Task(
        description=(
            "Synthesize the Analysis and Research into structured Feature Specifications. "
            "Use 'read_template' to get the structure and 'write_feature' to save each one. "
            "Ensure 'F-XXX' numbering is correct by using 'get_next_id'. "
            "IMPORTANT: Use the current date (2026-03-08) for the 'created_at' field in the specifications."
        ),
        expected_output="Confirmation of the new feature specifications written to the backlog.",
        agent=po,
        context=[research_task]
    )

    # Crew
    crew = Crew(
        agents=[analyst, researcher, po],
        tasks=[analysis_task, research_task, backlog_task],
        process=Process.sequential,
        verbose=True
    )

    print(f"### Starting Strategic Review for: {target_path} ###")
    return crew.kickoff()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the CrewAI Strategic Reviewer.")
    parser.add_argument("--target", required=True, help="The file or directory to analyze.")
    args = parser.parse_args()

    run_strategic_crew(args.target)
