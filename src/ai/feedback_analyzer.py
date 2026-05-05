"""Feedback analyzer for learning from user ratings and suggesting improvements."""

from typing import List, Dict, Any, Tuple
from collections import defaultdict
from datetime import datetime

from ..models import FeedbackSignal, SourceType
from ..storage.manager import StorageManager


class FeedbackAnalyzer:
    """Analyzes user feedback to identify misscored items and suggest prompt improvements."""

    def __init__(self, storage: StorageManager):
        self.storage = storage

    def get_feedback_summary(self, profile_name: str) -> Dict[str, Any]:
        """Get summary of feedback and scoring accuracy for a profile."""
        stats = self.storage.get_feedback_stats(profile_name)

        return {
            "total_feedback": stats["total_feedback"],
            "positive_feedback": stats["positive"],
            "negative_feedback": stats["negative"],
            "favorites": stats["favorites"],
            "misscored_items": stats["misscored_items"],
            "accuracy_rate": f"{stats['accuracy_rate']:.1f}%",
            "summary": self._format_summary(stats),
        }

    def _format_summary(self, stats: Dict[str, Any]) -> str:
        """Generate a human-readable summary of stats."""
        if stats["total_feedback"] == 0:
            return "No feedback collected yet."

        accuracy = stats["accuracy_rate"]
        if accuracy >= 90:
            quality = "excellent"
        elif accuracy >= 80:
            quality = "good"
        elif accuracy >= 70:
            quality = "fair"
        else:
            quality = "needs improvement"

        return (
            f"Accuracy: {quality} ({accuracy:.0f}%). "
            f"👍 {stats['positive']} positive, "
            f"👎 {stats['negative']} negative, "
            f"⭐ {stats['favorites']} favorites. "
            f"⚠️ {stats['misscored_items']} items were misscored."
        )

    def analyze_misscored_patterns(self, profile_name: str) -> Dict[str, Any]:
        """Analyze patterns in misscored items to suggest improvements."""
        misscored = self.storage.get_misscored_items(profile_name)

        if not misscored:
            return {
                "patterns": [],
                "recommendations": ["Keep current scoring! No significant misses detected."],
            }

        # Categorize misses
        too_low = [m for m in misscored if m["user_rating"] == 1]  # Rated 👍 but scored low
        too_high = [m for m in misscored if m["user_rating"] == -1]  # Rated 👎 but scored high

        patterns = []
        recommendations = []

        # Analyze too-low scores
        if too_low:
            avg_score = sum(m["ai_score_at_feedback"] for m in too_low) / len(too_low)
            patterns.append(
                {
                    "type": "underscored_items",
                    "count": len(too_low),
                    "avg_score": round(avg_score, 1),
                    "description": f"Items rated 👍 but scored low ({len(too_low)} cases)",
                }
            )
            recommendations.append(
                f"Consider raising thresholds by ~{5 - round(avg_score, 1):.0f} points for low-scoring items that users love."
            )

        # Analyze too-high scores
        if too_high:
            avg_score = sum(m["ai_score_at_feedback"] for m in too_high) / len(too_high)
            patterns.append(
                {
                    "type": "overscored_items",
                    "count": len(too_high),
                    "avg_score": round(avg_score, 1),
                    "description": f"Items rated 👎 but scored high ({len(too_high)} cases)",
                }
            )
            recommendations.append(
                f"Consider being more critical: lower threshold by ~{round(avg_score, 1) - 5:.0f} points for high-scoring items users dislike."
            )

        return {
            "patterns": patterns,
            "recommendations": recommendations,
            "misscored_count": len(misscored),
            "total_feedback": len(misscored) + len([m for m in misscored if True]),  # Placeholder
        }

    def suggest_source_specific_adjustments(self, profile_name: str) -> Dict[str, List[str]]:
        """Analyze feedback by source to suggest source-specific prompt adjustments."""
        misscored = self.storage.get_misscored_items(profile_name)

        if not misscored:
            return {}

        # Group misses by source (from item_id format: {source}:{subtype}:{native_id})
        by_source = defaultdict(list)
        for miss in misscored:
            parts = miss["item_id"].split(":", 1)
            if parts:
                source = parts[0]
                by_source[source].append(miss)

        suggestions = {}
        for source, misses in by_source.items():
            too_low = len([m for m in misses if m["user_rating"] == 1])
            too_high = len([m for m in misses if m["user_rating"] == -1])

            source_suggestions = []

            if too_low > 1:
                source_suggestions.append(
                    f"🔼 {source.upper()}: {too_low} items rated 👍 were underscored. "
                    f"Adjust the {source.upper()} scoring prompt to value engagement/novelty more."
                )

            if too_high > 1:
                source_suggestions.append(
                    f"🔽 {source.upper()}: {too_high} items rated 👎 were overscored. "
                    f"Adjust the {source.upper()} scoring prompt to be more critical."
                )

            if source_suggestions:
                suggestions[source] = source_suggestions

        return suggestions

    def get_improvement_roadmap(self, profile_name: str) -> List[Dict[str, Any]]:
        """Generate a prioritized list of improvements based on feedback."""
        stats = self.storage.get_feedback_stats(profile_name)
        patterns = self.analyze_misscored_patterns(profile_name)
        source_suggestions = self.suggest_source_specific_adjustments(profile_name)

        if stats["total_feedback"] < 5:
            return [
                {
                    "priority": "info",
                    "title": "More feedback needed",
                    "description": f"Collect {5 - stats['total_feedback']} more feedback ratings to enable suggestions.",
                }
            ]

        roadmap = []

        # Add pattern-based improvements
        for pattern in patterns["patterns"]:
            roadmap.append(
                {
                    "priority": "high" if pattern["count"] > 3 else "medium",
                    "title": pattern["description"],
                    "action": patterns["recommendations"][len(roadmap)],
                }
            )

        # Add source-specific improvements
        for source, suggestions in source_suggestions.items():
            for suggestion in suggestions:
                roadmap.append(
                    {
                        "priority": "medium",
                        "title": f"Source: {source}",
                        "action": suggestion,
                    }
                )

        return sorted(roadmap, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["priority"], 3))

    def export_feedback_to_csv(self, profile_name: str, output_path: str) -> None:
        """Export all feedback for a profile to CSV."""
        import csv

        misscored = self.storage.get_misscored_items(profile_name)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["item_id", "rating", "ai_score", "notes", "timestamp"],
            )
            writer.writeheader()
            for miss in misscored:
                writer.writerow(
                    {
                        "item_id": miss["item_id"],
                        "rating": "👍" if miss["user_rating"] == 1 else "👎",
                        "ai_score": miss["ai_score_at_feedback"],
                        "notes": miss["notes"] or "",
                        "timestamp": miss["timestamp"],
                    }
                )
