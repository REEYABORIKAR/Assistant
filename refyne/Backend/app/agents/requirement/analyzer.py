"""
Requirement Agent Analyzer.

Interprets the retrieved context and user request to build a generation plan.
Determines what document type to generate and configures the appropriate prompt.
"""
import logging

from app.agents.requirement.schema import GenerationPlan
from app.agents.supervisor.state import Intent, SupervisorState
from app.api.document_generation import DOCUMENT_PROMPTS

logger = logging.getLogger(__name__)

# Intent to action mapping (mirrors orchestrator's INTENT_TO_ACTION)
INTENT_TO_ACTION: dict[Intent, str] = {
    Intent.BRD_GENERATION: "brd",
    Intent.SRS_GENERATION: "srs",
    Intent.RTM_GENERATION: "rtm",
    Intent.USER_STORY_GENERATION: "user_stories",
    Intent.ACCEPTANCE_CRITERIA_GENERATION: "acceptance_criteria",
    Intent.REQUIREMENT_GENERATION: "brd",
    Intent.REVISION: "brd",
}

# Intent to output type mapping
INTENT_TO_OUTPUT_TYPE: dict[Intent, str] = {
    Intent.BRD_GENERATION: "brd",
    Intent.SRS_GENERATION: "srs",
    Intent.RTM_GENERATION: "rtm",
    Intent.USER_STORY_GENERATION: "user_stories",
    Intent.ACCEPTANCE_CRITERIA_GENERATION: "acceptance_criteria",
    Intent.REQUIREMENT_GENERATION: "generic",
    Intent.REVISION: "generic",
}


def resolve_action(state: SupervisorState) -> str:
    """
    Determine the document generation action for this state.

    Priority:
      1. state.action (explicit action from frontend/API)
      2. INTENT_TO_ACTION mapping (from classified intent)
      3. Fallback to "brd"
    """
    if state.action:
        return state.action
    return INTENT_TO_ACTION.get(state.intent, "brd")


def build_generation_plan(state: SupervisorState) -> GenerationPlan | None:
    """
    Analyze the state and build a generation plan.

    Returns None if no action can be resolved.
    """
    action = resolve_action(state)
    action_config = DOCUMENT_PROMPTS.get(action)

    if not action_config:
        logger.warning(f"No document prompt config for action: {action}")
        return None

    output_type = INTENT_TO_OUTPUT_TYPE.get(state.intent, "generic")

    plan = GenerationPlan(
        action=action,
        title=action_config["title"],
        prompt=action_config["prompt"],
        top_k=10,
        output_type=output_type,
    )

    logger.info(
        f"Generation plan: action={plan.action}, output_type={plan.output_type}, "
        f"title={plan.title}"
    )
    return plan
