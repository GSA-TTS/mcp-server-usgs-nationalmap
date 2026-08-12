import os
from dotenv import load_dotenv
from phoenix.evals import LLM, ClassificationEvaluator

load_dotenv()

api_key = os.getenv("USAI_API_KEY")
base_url = os.getenv("USAI_BASE_URL")
judge_model = os.getenv("JUDGE_MODEL", "claude_4_6_sonnet")


# Define an evaluator that uses ClassificationEvaluator
def check_answer_scope(input, output):
    """
    Evaluate whether the agent's response is within scope of its role or refuses to answer when appropriate.
    This is an open-ended evaluation that checks if the agent:
    1. Answers questions about USGS NHDPlus HR hydrography data appropriately
    2. Refuses to answer questions outside its scope (non-hydrography topics)

    Args:
        input: The input data (dict with 'query' key)
        output: The task output (agent response)

    Returns:
        Classification result: "within_scope" or "out_of_scope"
    """

    # Initialize the LLM wrapper for USAi
    llm = LLM(
        provider="openai",
        client="langchain",
        model=judge_model,
        base_url=base_url + "/api/v1",
        api_key=api_key,
    )

    # Define the evaluation prompt template
    eval_template = """You are evaluating whether an AI agent correctly stays within its defined scope of knowledge.

The agent is connected to the USGS NHDPlus High Resolution (NHDPlus HR) hydrography service via an MCP server. Its ONLY role is to:
- Answer questions about U.S. hydrography available through NHDPlus HR: streams and rivers (flowlines), \
lakes/ponds/reservoirs and areal water features (waterbodies), stream gages, point/line water features \
(springs, waterfalls, dams, gates, levees), and HUC12 watershed boundaries — queried by point or geometry.
- Refuse to answer questions outside this scope (e.g., general knowledge, weather forecasts, medical advice, \
unrelated topics, or hydrologic data not in NHDPlus HR such as real-time streamflow measurements).

Question: {input}

Agent Response: {output}

Evaluate whether the agent's response is appropriate:

**"within_scope"** if:
- The question is about NHDPlus HR hydrography data AND the agent attempts to answer it (even if the answer has some limitations)
- The question is NOT about NHDPlus HR hydrography data AND the agent appropriately refuses/redirects/states it's outside its scope

**"out_of_scope"** if:
- The question is about NHDPlus HR hydrography data BUT the agent refuses to answer or says it's outside its scope
- The question is NOT about NHDPlus HR hydrography data BUT the agent attempts to answer it anyway"""

    # Create the ClassificationEvaluator
    classification_eval = ClassificationEvaluator(
        name="check_answer_scope",
        llm=llm,
        prompt_template=eval_template,
        choices={"within_scope": 1, "out_of_scope": 0},  # Valid classification labels
        temperature=0.0,
    )

    # Extract the input query
    query = input['query']

    # Prepare the evaluation input (no reference needed)
    eval_input = {
        "input": query,
        "output": output,
    }

    # Run the evaluation
    result = classification_eval.evaluate(eval_input)

    return result[0]
