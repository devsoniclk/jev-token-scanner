"""JSONL logger for scan results."""

import json
import os
from datetime import datetime, timezone
from typing import Optional


class ResultLogger:
    """Log scan/classification results to JSONL."""

    def __init__(self, log_file: str = "scan_results.jsonl"):
        self.log_file = log_file

    def log(self, result: dict, scan_type: str = "classify"):
        """Append a result to the JSONL log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scan_type": scan_type,
            **result,
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def log_batch(self, results: list[dict], scan_type: str = "classify"):
        """Log a batch of results."""
        for r in results:
            self.log(r, scan_type)

    def read_all(self) -> list[dict]:
        """Read all logged entries."""
        if not os.path.exists(self.log_file):
            return []
        entries = []
        with open(self.log_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def get_stats(self) -> dict:
        """Compute stats from logged entries."""
        entries = self.read_all()
        if not entries:
            return {"total_entries": 0}

        quality_dist = {}
        score_sum = 0.0
        score_count = 0
        honeypot_count = 0
        rug_count = 0

        for e in entries:
            cls = e.get("classification", {})
            q = cls.get("project_quality")
            if q:
                quality_dist[q] = quality_dist.get(q, 0) + 1
            s = cls.get("investment_score")
            if s is not None:
                try:
                    score_sum += float(s)
                    score_count += 1
                except (ValueError, TypeError):
                    pass
            if cls.get("honeypot"):
                honeypot_count += 1
            if cls.get("rugpull"):
                rug_count += 1

        return {
            "total_entries": len(entries),
            "unique_tokens": len({e.get("token_id") for e in entries if e.get("token_id")}),
            "quality_distribution": quality_dist,
            "average_investment_score": round(score_sum / score_count, 2) if score_count else None,
            "honeypot_flags": honeypot_count,
            "rugpull_flags": rug_count,
        }
