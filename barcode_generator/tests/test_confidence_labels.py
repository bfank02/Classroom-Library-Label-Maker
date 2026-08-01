"""Tests for user-facing confidence labels on ReviewCandidate (Phase 4.1.1)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from classroom_library_label_maker.models import (
    CONFIDENCE_LABEL_HIGH,
    CONFIDENCE_LABEL_MEDIUM,
    CONFIDENCE_LABEL_VERY_HIGH,
    ReviewCandidate,
    confidence_label_for_score,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1.0, "Very High"),
        (CONFIDENCE_LABEL_VERY_HIGH, "Very High"),
        (CONFIDENCE_LABEL_VERY_HIGH - 1e-9, "High"),
        (CONFIDENCE_LABEL_HIGH, "High"),
        (CONFIDENCE_LABEL_HIGH - 1e-9, "Medium"),
        (CONFIDENCE_LABEL_MEDIUM, "Medium"),
        (CONFIDENCE_LABEL_MEDIUM - 1e-9, "Low"),
        (0.0, "Low"),
        (-0.1, "Low"),
    ],
)
def test_confidence_label_for_score_thresholds(
    score: float,
    expected: str,
) -> None:
    assert confidence_label_for_score(score) == expected


def test_review_candidate_confidence_label_property() -> None:
    candidate = ReviewCandidate(
        title="Ocean Adventure",
        author="Pat Lee",
        confidence_score=0.91,
    )
    assert candidate.confidence_label == "Very High"
    assert f"{candidate.confidence_label} Match" == "Very High Match"

    medium = ReviewCandidate(confidence_score=0.75)
    assert medium.confidence_label == "Medium"
    assert f"{medium.confidence_label} Match" == "Medium Match"

    low = ReviewCandidate(confidence_score=0.5)
    assert low.confidence_label == "Low"


def test_review_candidate_score_is_immutable() -> None:
    candidate = ReviewCandidate(confidence_score=0.85)
    try:
        candidate.confidence_score = 0.1  # type: ignore[misc]
        raised = False
    except FrozenInstanceError:
        raised = True
    assert raised


def test_review_candidate_to_dict_includes_score_and_label() -> None:
    payload = ReviewCandidate(
        isbn13="9781111111111",
        title="Ocean Adventure",
        author="Pat Lee",
        confidence_score=0.85,
    ).to_dict()
    assert payload["confidence_score"] == 0.85
    assert payload["confidence_label"] == "High"
    assert "confidence" not in payload
