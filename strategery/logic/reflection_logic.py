"""
REFLECTION LOGIC: Core functions for Rubric-Driven Reflection (F-031).
Mandate: Decouple reasoning/validation logic from orchestration for 100% testability.
"""
import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from strategery.strategic_logger import strategic_logger


class RubricCriterion(BaseModel):
    name: str
    description: str
    weight: float = 1.0

class ValidationRubric(BaseModel):
    task_goal: str
    criteria: List[RubricCriterion]
    success_threshold: float = 0.9

class CriticScore(BaseModel):
    criterion_name: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str

class CriticReport(BaseModel):
    overall_score: float
    scores: List[CriticScore]
    passed: bool
    feedback: str
    required_corrections: List[str] = []

def generate_rubric_prompt(task: str) -> str:
    """Generates a prompt to ask the model for a JSON validation rubric."""
    return f"""### 🛡️ TASK VALIDATION RUBRIC GENERATION
You are a high-precision architect. Before executing the following task, you must define the measurable criteria for success.

**TASK:** {task}

**YOUR JOB:**
Generate a JSON object representing a 'ValidationRubric'. 
Identify 3-5 specific, measurable criteria that would prove this task was completed correctly and without hallucinations.

**JSON SCHEMA:**
{{
  "task_goal": "A concise summary of the end state",
  "criteria": [
    {{ "name": "Criterion Name", "description": "How to verify this specifically", "weight": 1.0 }}
  ],
  "success_threshold": 0.9
}}

**OUTPUT ONLY THE JSON OBJECT.**
"""

def generate_critic_prompt(task: str, rubric: Dict[str, Any], proposed_answer: str) -> str:
    """Generates a prompt for the Critic turn to audit the specialist's output."""
    rubric_json = json.dumps(rubric, indent=2)
    return f"""### 🛡️ STRATEGIC CRITIC TURN
You are a high-reasoning auditor. You must evaluate the Specialist's performance against the provided Validation Rubric.

**ORIGINAL TASK:**
{task}

**VALIDATION RUBRIC:**
{rubric_json}

**PROPOSED ANSWER / OUTPUT:**
{proposed_answer}

**YOUR JOB:**
1. Audit the proposed answer against EVERY criterion in the rubric.
2. Be extremely critical. Penalize missing evidence, hallucinations, or "vibes-based" plans instead of execution.
3. Calculate an overall_score (0.0 to 1.0) as a weighted average.
4. Identify 'required_corrections' if any criteria score below 0.8.

**OUTPUT ONLY A JSON OBJECT matching this schema:**
{{
  "overall_score": 0.85,
  "scores": [
    {{ "criterion_name": "Name", "score": 0.7, "reasoning": "Why this score?" }}
  ],
  "passed": false,
  "feedback": "Concise summary of quality",
  "required_corrections": ["Specific thing to fix", "Another fix"]
}}
"""

def parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """Robustly extracts and parses JSON from a model's response."""
    if not text:
        return None

    # 1. Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Extract from markdown code blocks
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Last resort: simple regex cleanup for leading/trailing text
    try:
        json_match = re.search(r"(\{[\s\S]*\})", text)
        if json_match:
            return json.loads(json_match.group(1).strip())
    except Exception as e:
        strategic_logger.debug(f"Reflection Logic: JSON extraction failed: {e}")

    return None

def calculate_total_score(report_data: Dict[str, Any], rubric_data: Dict[str, Any]) -> float:
    """Recalculates the weighted total score from a critic report to ensure honesty."""
    try:
        criteria_weights = {c['name']: c.get('weight', 1.0) for c in rubric_data.get('criteria', [])}
        total_weight = sum(criteria_weights.values())

        if total_weight == 0: return 0.0

        weighted_sum = 0.0
        for score_item in report_data.get('scores', []):
            name = score_item.get('criterion_name')
            score = score_item.get('score', 0.0)
            weight = criteria_weights.get(name, 1.0)
            weighted_sum += (score * weight)

        return round(weighted_sum / total_weight, 3)
    except Exception as e:
        strategic_logger.error(f"Reflection Logic: Score calculation failed: {e}")
        return 0.0
