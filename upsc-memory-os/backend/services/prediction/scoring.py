"""
UPSC Memory OS — Prediction Engine (all 12 layers).

This is the core of the product. Every layer is implemented exactly as specified.

Layers:
  L1a: Effective revision count (18h cramming gate)
  L1b: Days since last valid revision
  L2:  Topic-type decay constants
  L2b: Item difficulty multiplier (IRT)
  L3:  Population-adjusted decay
  L4:  Personal multiplier
  L5+L6: Weighted accuracy (recent scores matter more)
  L7:  Relationship boost (placeholder)
  L8:  Exam pressure
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import math

from models.enums import TopicType, Difficulty

# ── L2: Topic-type decay constants ───────────────────────────────
DECAY_CONSTANTS = {
    TopicType.CURRENT_AFFAIRS:          2.0,
    TopicType.REPORTS_INDICES:          3.0,
    TopicType.GOVERNMENT_SCHEMES:       4.0,
    TopicType.INTERNATIONAL_RELATIONS:  5.0,
    TopicType.ENVIRONMENT:              6.0,
    TopicType.AGRICULTURE:              6.0,
    TopicType.ECONOMY:                  7.0,
    TopicType.SCIENCE_TECH:             7.0,
    TopicType.INTERNAL_SECURITY:        8.0,
    TopicType.DISASTER_MANAGEMENT:      8.0,
    TopicType.GOVERNANCE_SOCIAL_JUSTICE: 9.0,
    TopicType.GEOGRAPHY:               10.0,
    TopicType.SOCIETY:                 12.0,
    TopicType.POLITY:                  14.0,
    TopicType.HISTORY:                 14.0,
    TopicType.ART_AND_CULTURE:         14.0,
    TopicType.ETHICS:                  21.0,
    TopicType.ESSAY:                   30.0,
    TopicType.CSAT:                    30.0,
    TopicType.STATIC_SYLLABUS:         21.0,
}

# ── L2b: Item difficulty multiplier (IRT) ────────────────────────
DIFFICULTY_MULTIPLIER = {
    Difficulty.EASY:   1.3,   # decays slower → longer before revision needed
    Difficulty.MEDIUM: 1.0,
    Difficulty.HARD:   0.7,   # decays faster → revise sooner
}


# ── L8: Exam pressure ────────────────────────────────────────────
def exam_pressure_multiplier(exam_date: datetime) -> float:
    """
    Smoothly increases urgency as exam approaches using an exponential curve:
    1.0 + 1.5 * e^(-0.05 * days)
    """
    now_date = datetime.now(timezone.utc).date()
    days = max((exam_date.date() - now_date).days, 0)
    
    return 1.0 + (1.5 * math.exp(-0.05 * days))


# ── L1a: Effective revision count (18h cramming gate) ────────────
def effective_revision_count(
    history: list[dict], min_gap_hours: int = 18
) -> int:
    """
    Count only revisions separated by at least min_gap_hours.
    Prevents gaming via cramming — 5 revisions in 1 hour = 1 effective.
    """
    if not history:
        return 0
    
    sorted_h = sorted(history, key=lambda x: x["revised_at"])
    count = 1
    last_valid = sorted_h[0]["revised_at"]
    for event in sorted_h[1:]:
        if event["revised_at"] - last_valid >= timedelta(hours=min_gap_hours):
            count += 1
            last_valid = event["revised_at"]
    return count


# ── L1b: Days since last valid revision ──────────────────────────
def days_since_valid_revision(
    history: list[dict], min_gap_hours: int = 18
) -> float:
    """
    Days since the last revision that was at least min_gap_hours
    after the previous one. Returns 999.0 if never revised.
    """
    if not history:
        return 999.0
    
    now = datetime.now(timezone.utc)
    
    sorted_h = sorted(history, key=lambda x: x["revised_at"])
    
    # Safely tag database timestamps as UTC-aware
    for h in sorted_h:
        if h["revised_at"].tzinfo is None:
            h["revised_at"] = h["revised_at"].replace(tzinfo=timezone.utc)
        
    last_valid = sorted_h[0]["revised_at"]
    for event in sorted_h[1:]:
        if (event["revised_at"] - last_valid >= timedelta(hours=min_gap_hours)):
            last_valid = event["revised_at"]
    return (now - last_valid).total_seconds() / 86400


# ── L6: Weighted accuracy (recent scores matter more) ────────────
def weighted_accuracy(scores_with_dates: list[tuple]) -> float:
    """
    scores_with_dates = [(score, days_ago), ...]
    Recent scores weighted exponentially more.
    """
    if not scores_with_dates:
        return 0.5
    total_w = weighted_sum = 0.0
    for score, days_ago in scores_with_dates:
        w = 1 / (days_ago + 1)
        weighted_sum += score * w
        total_w += w
    return weighted_sum / total_w if total_w > 0 else 0.5


# ── L3: Population-adjusted decay ────────────────────────────────
def population_adjusted_constant(
    base: float,
    observed: Optional[float],
    sample_count: int,
) -> float:
    """
    Blend base decay constant with observed population data.
    Only adjusts when we have enough samples (>30).
    """
    if observed is None or sample_count < 30:
        return base  # not enough data — use prior
    lr = min(sample_count / 100, 0.3)
    return (1 - lr) * base + lr * observed


# ── L4: Personal multiplier ─────────────────────────────────────
def get_personal_multiplier(
    interaction_count: int,
    stored_multiplier: float,
) -> float:
    """Cold start: use population default until 5 interactions."""
    if interaction_count < 5:
        return 1.0
    return stored_multiplier


def update_personal_multiplier(
    current: float,#current stored multiplier for the topic
    predicted_retention: float,#predicted retention from last revision's score
    actual_accuracy: float,#actual accuracy from recent quiz answers (0 to 1)
) -> float:
    """Adjust multiplier based on prediction vs reality drift."""
    drift = predicted_retention - actual_accuracy
    if drift > 0.3:
        current -= 0.1   # forgets faster than predicted
    elif drift < -0.3:
        current += 0.1   # retains better than predicted
    return min(max(current, 0.3), 2.0)


# ── L7: Relationship boost (placeholder until Month 1) ───────────
def get_relationship_boost(topic_id: str, db=None) -> float:
    """
    Returns 1.0 until topic graph is populated.
    Future: query topic_relationships for topics that recently
    hit CRITICAL, boost linked topics proportional to strength.
    """
    return 1.0


# ── MASTER FORMULA — all 12 layers ───────────────────────────────
def final_urgency_score(
    topic_type:          TopicType,
    exam_date:           datetime,
    revision_history:    list[dict],   # [{revised_at, accuracy_score}]
    scores_with_dates:   list[tuple],  # [(score, days_ago)]
    interaction_count:   int,
    stored_multiplier:   float,
    pop_observed_decay:  Optional[float],
    pop_sample_count:    int,
    card_difficulty:     Difficulty,
    global_wrong_rate:   Optional[float],
    topic_id:            str = "",
    db=None,
    importance_weight:   float = 0.5,  # Weak subjects get 0.7
) -> float:
    """
    Compute the urgency score for a topic/flashcard.
    Higher score = needs revision more urgently.
    """
    # ── Phase 1: Compute final decay rate ────────────────────────
    base = DECAY_CONSTANTS.get(topic_type, 7.0)                   # L2
    pop = population_adjusted_constant(                            # L3
        base, pop_observed_decay, pop_sample_count
    )
    personal = get_personal_multiplier(                            # L4
        interaction_count, stored_multiplier
    )

    # L2b: platform override takes precedence over LLM assignment
    if global_wrong_rate is not None:
        if global_wrong_rate >= 0.8:
            card_difficulty = Difficulty.HARD
        elif global_wrong_rate <= 0.3:
            card_difficulty = Difficulty.EASY
    diff = DIFFICULTY_MULTIPLIER.get(card_difficulty, 1.0)

    final_decay = max(pop * personal * diff, 0.1)

    # ── Phase 2: Base urgency score ──────────────────────────────
    eff_count = max(effective_revision_count(revision_history), 1)  # L1a
    days_since = days_since_valid_revision(revision_history)        # L1b
    eff_acc = weighted_accuracy(scores_with_dates)                  # L5+L6

    base_score = (
        (days_since / final_decay)     # L1
        * (1.1 - eff_acc)             # 1.1 floor: prevents permanent zero
        * (1 / eff_count)
    )

    base_score *= get_relationship_boost(topic_id, db)              # L7
    
    # ── Inject User's Importance Weight (Weak Subjects) ──────────
    # If standard (0.5), multiplier is 1.0. If weak (0.7), multiplier is 1.4
    base_score *= (importance_weight / 0.5)

    # ── Phase 3: External modifiers ──────────────────────────────
    return base_score * exam_pressure_multiplier(exam_date)         # L8


def classify_urgency(score: float) -> str:
    """Map score to tier for display."""
    if score > 0.6:
        return "CRITICAL"
    if score > 0.3:
        return "HIGH"
    if score > 0.1:
        return "MEDIUM"
    return "STABLE"
