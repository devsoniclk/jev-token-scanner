"""Jev OpenRouter client — sends token state and questions for classification."""

import os
import requests
from typing import Optional


class JevClient:
    """Client for Jev (typesafe/jev-1.13) via OpenRouter decisions API."""

    def __init__(self, config: dict, api_key: Optional[str] = None):
        self.url = config["jev"]["openrouter_url"]
        self.model = config["jev"]["model"]
        self.questions = config["jev"]["questions"]
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")

    def classify(self, token_state: dict) -> dict:
        """
        Send token state + questions to Jev and return the decision.

        Args:
            token_state: dict with token info (name, symbol, market_cap, etc.)

        Returns:
            dict with question_id -> answer mapping, plus raw response.
        """
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")

        payload = {
            "model": self.model,
            "state": token_state,
            "questions": self.questions,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/jev-token-scanner",
            "X-Title": "Jev Token Scanner",
        }

        resp = requests.post(self.url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # Parse Jev response — extract decisions
        result = self._parse_response(data)
        result["raw_response"] = data
        return result

    def _parse_response(self, data: dict) -> dict:
        """Parse Jev API response into structured answers."""
        result = {}
        decisions = data.get("decisions", data.get("answers", []))

        if isinstance(decisions, list):
            for i, q in enumerate(self.questions):
                qid = q["id"]
                if i < len(decisions):
                    result[qid] = decisions[i]
                else:
                    result[qid] = None
        elif isinstance(decisions, dict):
            # If Jev returns a dict keyed by question id
            for q in self.questions:
                result[q["id"]] = decisions.get(q["id"])

        # Fallback: check top-level keys
        for q in self.questions:
            if q["id"] not in result:
                result[q["id"]] = data.get(q["id"])

        return result
