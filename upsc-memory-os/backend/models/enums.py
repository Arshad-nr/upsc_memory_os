"""Centralized domain Enums for UPSC Memory OS.

All modules that need TopicType or Difficulty must import from here.
This prevents duplicate definitions and guarantees type consistency
across the database, ingestion pipeline, prediction engine, and API.
"""

from enum import Enum


class TopicType(str, Enum):
    """Maps 1:1 to the real UPSC Mains syllabus structure."""

    # Dynamic / Current
    CURRENT_AFFAIRS = "current_affairs"
    GOVERNMENT_SCHEMES = "government_schemes"
    REPORTS_INDICES = "reports_indices"

    # GS 1
    HISTORY = "history"
    ART_AND_CULTURE = "art_and_culture"
    GEOGRAPHY = "geography"
    SOCIETY = "society"

    # GS 2
    POLITY = "polity"
    GOVERNANCE_SOCIAL_JUSTICE = "governance_social_justice"
    INTERNATIONAL_RELATIONS = "international_relations"

    # GS 3
    ECONOMY = "economy"
    AGRICULTURE = "agriculture"
    ENVIRONMENT = "environment"
    SCIENCE_TECH = "science_tech"
    INTERNAL_SECURITY = "internal_security"
    DISASTER_MANAGEMENT = "disaster_management"

    # GS 4 & Others
    ETHICS = "ethics"
    ESSAY = "essay"
    CSAT = "csat"

    # Catch-all
    STATIC_SYLLABUS = "static_syllabus"


class Difficulty(str, Enum):
    """Item difficulty for IRT-based decay multiplier."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ErrorType(str, Enum):
    """
    Self-reported error taxonomy — asked after every wrong answer.
    
    'Why did you get this wrong?'
    Each type carries a decay_weight that tells the prediction engine
    HOW MUCH to penalize the student's retention score.
    
    Higher weight = more aggressive re-scheduling.
    """

    COMPLETE_BLANK = "complete_blank"        # "I had no idea"
    CONFUSED_SIMILAR = "confused_similar"     # "I confused it with something"
    PARTIAL_RECALL = "partial_recall"         # "I partially remembered"
    CARELESS_MISTAKE = "careless_mistake"     # "Careless mistake"
    CORRECT = "correct"                       # Student got it right


# ── Error-Type Scoring Config ────────────────────────────────────
# Each error type maps to:
#   anchor: the student's implied true retention level (0.0 = no memory, 1.0 = perfect)
#   alpha:  how much we trust the student's self-report over the LLM's raw score (0.0–1.0)
#
# Formula: adjusted = (1 - alpha) * raw_score + alpha * anchor
#
# This lets the student's self-report push the score in EITHER direction:
#   - "complete_blank" pulls a lucky-keyword score DOWN toward 0
#   - "careless_mistake" rescues a typo-destroyed score UP toward 0.95
#   - "partial_recall" trusts the LLM entirely (alpha = 0)
ERROR_TYPE_CONFIG = {
    ErrorType.COMPLETE_BLANK:   {"anchor": 0.0,  "alpha": 0.9},
    ErrorType.CONFUSED_SIMILAR: {"anchor": 0.2,  "alpha": 0.7},
    ErrorType.PARTIAL_RECALL:   {"anchor": 0.5,  "alpha": 0.0},   # Trust the LLM
    ErrorType.CARELESS_MISTAKE: {"anchor": 0.95, "alpha": 0.8},
    ErrorType.CORRECT:          {"anchor": 1.0,  "alpha": 0.0},   # No adjustment
}
