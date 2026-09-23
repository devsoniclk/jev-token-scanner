"""Jev OpenRouter client — sends token state and questions for classification."""

import json
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

    @staticmethod
    def _format_questions(questions: list) -> dict:
        """Convert config questions to Jev API format.

        - 'choice' type: criteria must be {option: option} object
        - 'score'  type: criteria must be a list of strings
        - 'noul'   type: no criteria needed
        """
        out = {}
        for q in questions:
            qid = q["id"]
            entry: dict = {
                "type": q["type"],
                "instructions": q.get("question", ""),
            }
            if q["type"] == "choice":
                choices = q.get("choices", [])
                entry["criteria"] = {c: c for c in choices}
            elif q["type"] == "score":
                lo = q.get("min", 1)
                hi = q.get("max", 10)
                entry["criteria"] = [str(i) for i in range(lo, hi + 1)]
            # noul needs no criteria
            out[qid] = entry
        return out

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

        # state must be a string for Jev
        state_str = json.dumps(token_state) if isinstance(token_state, dict) else str(token_state)

        payload = {
            "model": self.model,
            "state": state_str,
            "questions": self._format_questions(self.questions),
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

    @staticmethod
    def _extract_value(answer) -> object:
        """Pull the scalar answer from a Jev answer dict.

        Jev returns e.g. {"type":"choice","choice":"legit",...} or
        {"type":"score","score":4.92,...} or {"type":"noul","noul":0.05}.
        """
        if not isinstance(answer, dict):
            return answer
        qtype = answer.get("type", "")
        if qtype == "choice":
            return answer.get("choice")
        if qtype == "score":
            return answer.get("score")
        if qtype == "noul":
            return answer.get("noul")
        # Fallback: first value that isn't 'type'
        for k, v in answer.items():
            if k != "type":
                return v
        return answer

    def _parse_response(self, data: dict) -> dict:
        """Parse Jev API response into structured answers."""
        result = {}
        decisions = data.get("decisions", data.get("answers", {}))

        if isinstance(decisions, dict):
            for q in self.questions:
                qid = q["id"]
                raw = decisions.get(qid)
                result[qid] = self._extract_value(raw)
        elif isinstance(decisions, list):
            for i, q in enumerate(self.questions):
                qid = q["id"]
                if i < len(decisions):
                    result[qid] = self._extract_value(decisions[i])
                else:
                    result[qid] = None

        # Fallback: check top-level keys
        for q in self.questions:
            if q["id"] not in result:
                result[q["id"]] = data.get(q["id"])

        return result
