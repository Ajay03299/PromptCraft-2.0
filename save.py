"""
ECHO//GARDEN // High-score persistence
======================================
Optional and failure-proof: a missing, empty, malformed or unwritable save file
silently falls back to an in-memory score. Saving can never crash the game.
"""

from __future__ import annotations

import json
import os

from config import SCORE_CAP


class HighScoreStore:
    def __init__(self, path: str | None) -> None:
        self.path = path
        self.memory = 0

    @staticmethod
    def default() -> "HighScoreStore":
        try:
            import pyxel

            folder = pyxel.user_data_dir("PromptCraft", "EchoGarden")
            return HighScoreStore(os.path.join(folder, "highscore.json"))
        except Exception:
            return HighScoreStore(None)

    def load(self) -> int:
        if not self.path:
            return self.memory
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            value = data.get("high_score", 0) if isinstance(data, dict) else 0
            if isinstance(value, bool) or not isinstance(value, int):
                value = 0
            self.memory = max(self.memory, max(0, min(value, SCORE_CAP)))
        except (OSError, ValueError, TypeError):
            pass
        return self.memory

    def save(self, score: int) -> bool:
        self.memory = max(self.memory, max(0, min(int(score), SCORE_CAP)))
        if not self.path:
            return False
        try:
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"high_score": self.memory, "version": 1}, fh)
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False
