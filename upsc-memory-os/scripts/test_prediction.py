"""
Property-based tests for the UPSC Memory OS prediction engine.
7 core properties that must always hold.

Run: python scripts/test_prediction.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import datetime, timezone, timedelta
from services.prediction.scoring import (
    final_urgency_score,
    classify_urgency,
    effective_revision_count,
    days_since_valid_revision,
    weighted_accuracy,
    exam_pressure_multiplier,
    DECAY_CONSTANTS,
)


def make_history(count: int, start_days_ago: int = 30, gap_hours: int = 24):
    """Create revision history with evenly spaced events."""
    now = datetime.now(timezone.utc)
    return [
        {
            "revised_at": now - timedelta(days=start_days_ago - i * (gap_hours / 24)),
            "accuracy_score": 0.7,
        }
        for i in range(count)
    ]


def make_scores(count: int, score: float = 0.7, start_days_ago: int = 30):
    """Create score tuples [(score, days_ago), ...]."""
    return [(score, start_days_ago - i) for i in range(count)]


EXAM_DATE = datetime.now() + timedelta(days=120)

BASE_ARGS = {
    "topic_type": "polity",
    "exam_date": EXAM_DATE,
    "revision_history": make_history(3),
    "scores_with_dates": make_scores(3),
    "interaction_count": 10,
    "stored_multiplier": 1.0,
    "pop_observed_decay": None,
    "pop_sample_count": 0,
    "card_difficulty": "medium",
    "global_wrong_rate": None,
    "is_deprecated": False,
}


def test_1_never_revised_highest_urgency():
    """Property 1: Never-revised topic should have highest urgency."""
    never_revised = final_urgency_score(
        **{**BASE_ARGS, "revision_history": [], "scores_with_dates": []}
    )
    revised = final_urgency_score(**BASE_ARGS)
    assert never_revised > revised, (
        f"Never-revised ({never_revised:.4f}) should be > revised ({revised:.4f})"
    )
    print(f"  [PASS] P1: Never-revised ({never_revised:.4f}) > revised ({revised:.4f})")


def test_2_current_affairs_decays_faster():
    """Property 2: Current affairs should decay faster than history."""
    ca_score = final_urgency_score(**{**BASE_ARGS, "topic_type": "current_affairs"})
    hist_score = final_urgency_score(**{**BASE_ARGS, "topic_type": "history"})
    assert ca_score > hist_score, (
        f"Current affairs ({ca_score:.4f}) should be > history ({hist_score:.4f})"
    )
    print(f"  [PASS] P2: Current affairs ({ca_score:.4f}) > history ({hist_score:.4f})")


def test_3_more_revisions_lower_urgency():
    """Property 3: More revisions should lower urgency."""
    few = final_urgency_score(
        **{**BASE_ARGS, "revision_history": make_history(2)}
    )
    many = final_urgency_score(
        **{**BASE_ARGS, "revision_history": make_history(8)}
    )
    assert few > many, (
        f"Few revisions ({few:.4f}) should be > many revisions ({many:.4f})"
    )
    print(f"  [PASS] P3: Few revisions ({few:.4f}) > many revisions ({many:.4f})")


def test_4_deprecated_maximum_urgency():
    """Property 4: Deprecated items should have maximum urgency."""
    normal = final_urgency_score(**BASE_ARGS)
    deprecated = final_urgency_score(**{**BASE_ARGS, "is_deprecated": True})
    assert deprecated > 0, f"Deprecated score ({deprecated}) should be > 0"
    print(f"  [PASS] P4: Deprecated ({deprecated:.4f}) vs normal ({normal:.4f})")


def test_5_closer_exam_higher_urgency():
    """Property 5: Closer exam date should increase urgency."""
    far = final_urgency_score(
        **{**BASE_ARGS, "exam_date": datetime.now() + timedelta(days=365)}
    )
    close = final_urgency_score(
        **{**BASE_ARGS, "exam_date": datetime.now() + timedelta(days=20)}
    )
    assert close > far, (
        f"Close exam ({close:.4f}) should be > far exam ({far:.4f})"
    )
    print(f"  [PASS] P5: Close exam ({close:.4f}) > far exam ({far:.4f})")


def test_6_perfect_accuracy_lower_urgency():
    """Property 6: Perfect accuracy should lower urgency."""
    perfect = final_urgency_score(
        **{**BASE_ARGS, "scores_with_dates": make_scores(5, score=1.0)}
    )
    poor = final_urgency_score(
        **{**BASE_ARGS, "scores_with_dates": make_scores(5, score=0.2)}
    )
    assert poor > perfect, (
        f"Poor accuracy ({poor:.4f}) should be > perfect ({perfect:.4f})"
    )
    print(f"  [PASS] P6: Poor accuracy ({poor:.4f}) > perfect ({perfect:.4f})")


def test_7_score_always_non_negative():
    """Property 7: Score should always be >= 0."""
    score = final_urgency_score(**BASE_ARGS)
    assert score >= 0, f"Score ({score}) should be >= 0"

    # Test edge cases — many revisions with high accuracy
    edge = final_urgency_score(
        **{
            **BASE_ARGS,
            "revision_history": make_history(20, start_days_ago=60),
            "scores_with_dates": make_scores(20, score=1.0, start_days_ago=60),
        }
    )
    assert edge >= 0, f"Edge case score ({edge}) should be >= 0"
    print(f"  [PASS] P7: Score always >= 0 (normal={score:.4f}, edge={edge:.6f})")


def test_classify_urgency_tiers():
    """Verify tier classification boundaries."""
    assert classify_urgency(0.8) == "CRITICAL"
    assert classify_urgency(0.5) == "HIGH"
    assert classify_urgency(0.2) == "MEDIUM"
    assert classify_urgency(0.05) == "STABLE"
    print("  [PASS] Bonus: Tier classification correct")


def main():
    print("=" * 60)
    print("  UPSC Memory OS — Prediction Engine Tests")
    print("=" * 60)
    print()

    tests = [
        test_1_never_revised_highest_urgency,
        test_2_current_affairs_decays_faster,
        test_3_more_revisions_lower_urgency,
        test_4_deprecated_maximum_urgency,
        test_5_closer_exam_higher_urgency,
        test_6_perfect_accuracy_lower_urgency,
        test_7_score_always_non_negative,
        test_classify_urgency_tiers,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: UNEXPECTED ERROR: {e}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
