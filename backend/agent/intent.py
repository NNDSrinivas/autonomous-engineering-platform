"""Lightweight intent detection for gating org-aware/tool agent runs.

This is deliberately simple keyword matching to decide when to trigger
the full agent pipeline (Org Brain, tools, edits). It keeps normal chat fast.
"""

from dataclasses import dataclass
from typing import List


ORG_KEYWORDS = [
    "jira",
    "ticket",
    "issue",
    "story",
    "scrum",
    "epic",
    "pr",
    "pull request",
    "merge request",
    "confluence",
    "wiki",
    "doc page",
    "slack",
    "channel",
    "threads",
    "teams",
    "meeting",
    "standup",
    "retro",
    "zoom",
    "recording",
    "transcript",
    "deployment",
    "deploy",
    "pipeline",
    "jenkins",
    "ci",
    "cd",
]


@dataclass
class DetectedIntent:
    org_aware: bool
    raw_keywords: List[str]


def detect_org_intent(message: str) -> DetectedIntent:
    text = (message or "").lower()
    hits = [kw for kw in ORG_KEYWORDS if kw in text]
    return DetectedIntent(org_aware=bool(hits), raw_keywords=hits)
