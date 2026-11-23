"""Published session outcomes: a classification, or verified non-classification."""

from __future__ import annotations


def no_classification(session: dict) -> bool:
    source = session.get("source") or {}
    return (
        session.get("type") in {"FP1", "FP2", "FP3"}
        and not session.get("results")
        and session.get("classificationStatus") == "not-issued"
        and session.get("classificationReason") == "no-timed-laps"
        and source.get("name") == "fia-official-timing"
        and str(source.get("url", "")).startswith("https://www.fia.com/sites/default/files/")
    )


def published_outcome(session: dict) -> bool:
    return bool(session.get("results")) or no_classification(session)


def prefer_session(previous: dict | None, fresh: dict) -> dict:
    """An empty response cannot undo a published outcome; actual rows take
    precedence over a non-classification notice."""
    if previous:
        if published_outcome(previous) and not published_outcome(fresh):
            return previous
        if previous.get("results") and not fresh.get("results"):
            return previous
        if (
            previous.get("results")
            and (previous.get("source") or {}).get("name") == "formula1-official"
            and (fresh.get("source") or {}).get("name") != "formula1-official"
        ):
            return previous
    return fresh
