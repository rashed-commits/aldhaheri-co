"""
Robust JSON parsing for model output. Handles three common failure modes
we've observed in practice:

  1. Output wrapped in ```json / ``` code fences (Haiku does this by default).
  2. JSON preceded or followed by a sentence of prose.
  3. Valid JSON with extra whitespace.
"""

import json
import re
from typing import Optional

# Matches the entire string as a code-fenced block: ```json ... ``` or ``` ... ```
_FENCE_RE = re.compile(r"^```(?:json|JSON)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)

# Matches the first {...} or [...] substring inside arbitrary text.
_BRACE_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_model_json(text: str) -> Optional[dict]:
    """Best-effort JSON extraction. Returns None on irrecoverable failure."""
    if not text:
        return None

    candidate = text.strip()

    # Strip a single ```json / ``` wrapper if present.
    fence = _FENCE_RE.match(candidate)
    if fence:
        candidate = fence.group(1).strip()

    # Direct parse.
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Last resort: pull out the first brace-balanced block we can find.
    brace = _BRACE_RE.search(candidate)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            return None
    return None
