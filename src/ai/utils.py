"""Shared AI utility functions."""

import ast
import json
import re
import unicodedata
from typing import Optional


def parse_json_response(response: Optional[str]) -> Optional[dict]:
    """Try multiple strategies to extract a JSON object from an AI response.

    Returns the parsed dict, or None if all strategies fail.
    """
    if response is None:
        return None
    text = _normalize_json_text(response)
    if not text:
        return None

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: extract from ```json ... ``` code block
    if "```json" in text:
        try:
            json_str = text.split("```json")[1].split("```")[0].strip()
            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    # Strategy 3: extract from ``` ... ``` code block
    if "```" in text:
        try:
            json_str = text.split("```")[1].split("```")[0].strip()
            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    # Strategy 4: find the first { ... } block using brace matching
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break

    # Strategy 5: regex extraction as last resort
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 6: permissive Python-literal fallback for JSON-like payloads.
    # This handles common LLM mistakes such as single quotes and trailing commas.
    if start != -1:
        try:
            candidate = _extract_json_candidate(text, start)
            candidate = _repair_json_like_text(candidate)
            parsed = ast.literal_eval(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError):
            pass

    return None


def _normalize_json_text(text: str) -> str:
    """Normalize common Unicode variants that break JSON parsing.

    This handles full-width punctuation, compatibility characters, and
    zero-width characters that some models occasionally emit.
    """
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"[\u200B-\u200D\uFEFF]", "", normalized)
    return normalized.strip()


def _extract_json_candidate(text: str, start: int) -> str:
    """Extract the most plausible JSON-like candidate from a text blob."""
    candidate = text[start:]
    last_brace = candidate.rfind("}")
    last_bracket = candidate.rfind("]")
    if last_brace == -1 and last_bracket == -1:
        return candidate

    if last_brace > last_bracket:
        return candidate[: last_brace + 1]
    return candidate[: last_bracket + 1]


def _repair_json_like_text(text: str) -> str:
    """Repair common JSON-like mistakes emitted by LLMs.

    This keeps the parser dependency-free while covering:
    - trailing commas
    - single-quoted strings
    - unquoted object keys
    - JSON booleans/null tokens
    """
    repaired = text.strip()
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    repaired = re.sub(r"(?<=\{|,)(\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*):", r'\1"\2"\3:', repaired)
    repaired = repaired.replace("true", "True").replace("false", "False").replace("null", "None")
    return repaired
