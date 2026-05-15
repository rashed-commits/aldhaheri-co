"""
Shared Anthropic client and model identifiers.

Sonnet for chat replies and manager routing; Haiku for everything lightweight
(skill matching, reflection, NL->cron parsing, task-type classification).
"""

import os

import anthropic

MODEL_SONNET = "claude-sonnet-4-6"
MODEL_HAIKU = "claude-haiku-4-5-20251001"

_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

client = anthropic.Anthropic(api_key=_API_KEY)
async_client = anthropic.AsyncAnthropic(api_key=_API_KEY)
