"""LLM output parsing utilities.

Shared parser for handling markdown code fences and JSON extraction
from LLM outputs across different backends.
"""

import json
import re
from typing import List, Dict, Any, Tuple, Literal


def parse_llm_actions(
    raw: str,
) -> Tuple[List[Dict[str, Any]], Literal["clean", "fenced", "invalid"]]:
    """Parse LLM output into action list with status tracking.

    Handles markdown code fences that models like qwen2.5-coder wrap JSON in.

    Args:
        raw: Raw text output from the LLM

    Returns:
        Tuple of (actions_list, status) where status is:
        - "clean": Valid JSON array parsed directly
        - "fenced": Valid JSON found inside markdown fence, stripped and recorded
        - "invalid": Could not parse as JSON array

    The returned actions_list contains dicts with keys: asset_id, action_type, value_kw
    """
    if not raw or not raw.strip():
        return [], "invalid"

    text = raw.strip()

    # Try direct JSON parse first (clean)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            # Validate each item has required fields
            valid = all(
                isinstance(item, dict) and "asset_id" in item and "value_kw" in item
                for item in parsed
            )
            if valid:
                return parsed, "clean"
        elif isinstance(parsed, dict) and "actions" in parsed:
            # Some models return {"actions": [...]}
            actions = parsed["actions"]
            if isinstance(actions, list):
                valid = all(
                    isinstance(item, dict) and "asset_id" in item and "value_kw" in item
                    for item in actions
                )
                if valid:
                    return actions, "clean"
    except json.JSONDecodeError:
        pass

    # Try to extract from markdown code fence (fenced)
    # Pattern: ```json\n[...]\n``` or ```\n[...]\n```
    fence_pattern = r"```(?:json)?\s*\n(.*?)\n```"
    matches = re.findall(fence_pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        # Take the first fenced block
        fenced_content = matches[0].strip()
        try:
            parsed = json.loads(fenced_content)
            if isinstance(parsed, list):
                valid = all(
                    isinstance(item, dict) and "asset_id" in item and "value_kw" in item
                    for item in parsed
                )
                if valid:
                    return parsed, "fenced"
            elif isinstance(parsed, dict) and "actions" in parsed:
                actions = parsed["actions"]
                if isinstance(actions, list):
                    valid = all(
                        isinstance(item, dict)
                        and "asset_id" in item
                        and "value_kw" in item
                        for item in actions
                    )
                    if valid:
                        return actions, "fenced"
        except json.JSONDecodeError:
            pass

    return [], "invalid"
