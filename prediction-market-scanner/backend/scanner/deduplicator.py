"""
Cross-platform deduplication: cluster the same real-world event
appearing on both Polymarket and Kalshi.
"""
from typing import Any
import re


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _jaccard(a: str, b: str, n: int = 3) -> float:
    """Jaccard similarity on character n-grams."""
    def ngrams(s: str) -> set[str]:
        return {s[i : i + n] for i in range(len(s) - n + 1)}

    sa, sb = ngrams(a), ngrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def deduplicate(markets: list[dict[str, Any]], similarity_threshold: float = 0.4) -> list[dict[str, Any]]:
    """
    Merge markets that appear on multiple platforms.
    Returns a deduplicated list; cross-platform matches have a
    `cross_platform` key with the counterpart's data.
    """
    poly = [m for m in markets if m["source"] == "polymarket"]
    kalshi = [m for m in markets if m["source"] == "kalshi"]

    merged: list[dict[str, Any]] = []
    matched_kalshi_ids: set[str] = set()

    for p in poly:
        pq = _normalize(p["question"])
        best_match = None
        best_score = 0.0

        for k in kalshi:
            kq = _normalize(k["question"])
            score = _jaccard(pq, kq)
            if score > best_score:
                best_score = score
                best_match = k

        if best_match and best_score >= similarity_threshold:
            matched_kalshi_ids.add(best_match["id"])
            combined = dict(p)
            combined["cross_platform"] = {
                "source": best_match["source"],
                "probability": best_match["probability"],
                "url": best_match["url"],
                "id": best_match["id"],
            }
            merged.append(combined)
        else:
            merged.append(p)

    # Add unmatched Kalshi markets
    for k in kalshi:
        if k["id"] not in matched_kalshi_ids:
            merged.append(k)

    # Sort by probability descending
    merged.sort(key=lambda m: m["probability"], reverse=True)
    return merged
