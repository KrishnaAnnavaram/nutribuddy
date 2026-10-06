"""Text and HTML output. Model text is never trusted as HTML: ``to_html`` escapes everything."""

from __future__ import annotations

import html

from .planner import DietPlan


def plan_to_text(plan: DietPlan) -> str:
    lines = [f"Diet plan: {plan.condition.display}", "", plan.summary, ""]
    if plan.foods:
        lines.append("Foods to include (amounts per 100 g, from the food store):")
        lines += [f"  - {f.describe()}" for f in plan.foods]
    if plan.foods_to_avoid:
        lines.append("Foods to limit or avoid: " + ", ".join(plan.foods_to_avoid))
    lines.append("")
    lines.append("Sources:")
    lines += [f"  [{n}] {plan.sources[n - 1].chunk.citation()}" for n in plan.cited]
    for w in plan.warnings:
        lines.append(f"Warning: {w}")
    lines += ["", plan.disclaimer]
    return "\n".join(lines)


def to_html(text: str) -> str:
    """Escape all text, then keep only line breaks. No tag from the model or the user survives."""
    return "<br>".join(html.escape(line) for line in text.splitlines())
