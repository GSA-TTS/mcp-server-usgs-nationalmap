import os
from dotenv import load_dotenv
from phoenix.evals import LLM, ClassificationEvaluator

load_dotenv()

api_key = os.getenv("USAI_API_KEY")
base_url = os.getenv("USAI_BASE_URL")
judge_model = os.getenv("JUDGE_MODEL", "claude_4_6_sonnet")

# Define an evaluator that uses ClassificationEvaluator
def match_expected_response(input, output, expected):
    """
    Evaluate the correctness of the agent's output by comparing it to the expected response.

    Args:
        input: The input data (dict with 'query' key)
        output: The task output (agent response)
        expected: The expected (reference) response to compare against (dict with 'responses' key)

    Returns:
        Classification result: "correct" or "incorrect"
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
    eval_template = """You are evaluating the correctness of an AI agent's response to a question about \
U.S. hydrography (streams, rivers, lakes, stream gages, water features, and watershed boundaries) \
sourced from the USGS NHDPlus High Resolution dataset.

Question: {input}

Expected Response: {reference}

Actual Response: {output}

Compare the actual response to the expected response. The expected response is the ground-truth \
answer (e.g. a watershed name, a HUC12 code, a stream order, a gage station name, a drainage area, \
or a True/False value). Determine if the actual response is correct based on whether it:
1. Contains the key value from the expected response (allow for reasonable formatting differences, \
   e.g. "1410 sq mi" matches "1410"; a HUC12 code matches regardless of surrounding text; a \
   waterbody/watershed name matches even if additional context is provided)
2. Is factually accurate and not contradicted by other statements in the response
3. Answers the question that was asked

Respond with ONLY "correct" or "incorrect" based on your evaluation."""

    # Create the ClassificationEvaluator
    classification_eval = ClassificationEvaluator(
        name="match_expected_response",
        llm=llm,
        prompt_template=eval_template,
        choices={"correct": 1, "incorrect": 0},  # Valid classification labels
        temperature=0.0,
    )

    # Extract the expected response
    expected_response = expected['responses']

    # Extract the input query
    query = input['query']

    # Prepare the evaluation input with all three components
    eval_input = {
        "input": query,
        "output": output,
        "reference": expected_response,
    }

    # Run the evaluation
    result = classification_eval.evaluate(eval_input)

    return result[0]
