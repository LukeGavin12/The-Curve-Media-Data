"""
Stage 5 — Brief Generation.

Generates an editorial brief for each accepted story cluster.
One Claude call per cluster, using CurveTOV.md as the system prompt.

Input:
  - Anchor article (title + summary) as the lead source
  - All other articles in the cluster as supporting context

Output:
  - brief written to story_clusters
  - cluster_status = briefed
  - briefed_at timestamp set
"""

import logging
from datetime import datetime, timezone
from typing import Any

import anthropic

from pipeline.config import ANTHROPIC_API_KEY
from pipeline.ingestion.storage import get_client, get_pipeline_settings, TABLE

logger = logging.getLogger(__name__)

CLUSTERS_TABLE = "story_clusters"
BRIEFING_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_accepted_clusters() -> list[dict[str, Any]]:
    client = get_client()
    response = (
        client.table(CLUSTERS_TABLE)
        .select("id, cluster_id, anchor_article_id")
        .eq("cluster_status", "accepted")
        .execute()
    )
    return response.data or []


def _fetch_cluster_articles(cluster_id: str) -> list[dict[str, Any]]:
    client = get_client()
    response = (
        client.table(TABLE)
        .select("id, guid, title, summary, source_name")
        .eq("cluster_id", cluster_id)
        .execute()
    )
    return response.data or []


# ---------------------------------------------------------------------------
# Brief generation
# ---------------------------------------------------------------------------

def _build_prompt(anchor: dict[str, Any], supporting: list[dict[str, Any]], brief_instructions: str = "") -> str:
    lines = [
        "Generate a short editorial name and brief for the following story.",
        "",
        "Return JSON only, with exactly two fields:",
        '  "name": the editorial title',
        '  "brief": the editorial brief',
        "",
    ]

    if brief_instructions:
        lines.append(brief_instructions)
        lines.append("")

    lines += [
        f"ANCHOR ARTICLE ({anchor.get('source_name', 'Unknown')}):",
        f"Title: {anchor.get('title', '')}",
        f"Summary: {anchor.get('summary', '')}",
    ]

    if supporting:
        lines.append("")
        lines.append("SUPPORTING ARTICLES:")
        for article in supporting:
            source = article.get("source_name", "Unknown")
            title = article.get("title", "")
            summary = article.get("summary", "")
            lines.append(f"- [{source}] {title}: {summary}")

    return "\n".join(lines)


def _generate_brief(anchor: dict[str, Any], supporting: list[dict[str, Any]], tov_doc: str, brief_instructions: str = "") -> tuple[str, str] | None:
    """
    Call Claude to generate a name and brief.
    Returns (name, brief) or None on failure.
    """
    import json

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = _build_prompt(anchor, supporting, brief_instructions)

    try:
        message = client.messages.create(
            model=BRIEFING_MODEL,
            max_tokens=600,
            system=tov_doc,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        name = data.get("name", "").strip()
        brief = data.get("brief", "").strip()
        if not name or not brief:
            raise ValueError("Missing name or brief in response")
        return name, brief
    except Exception as exc:
        logger.warning("Brief generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_briefing() -> None:
    """
    Stage 5 brief generation. Run after scoring.

    For each accepted cluster:
      1. Fetch anchor article + supporting articles
      2. Generate brief via Claude (CurveTOV.md as system prompt)
      3. Write brief to story_clusters
      4. Set cluster_status = briefed, briefed_at = now
    """
    logger.info("Brief generation started")

    _settings = get_pipeline_settings()
    _CURVE_TOV = _settings.get("tov_doc", "")
    _BRIEF_INSTRUCTIONS = _settings.get("brief_instructions", "")

    clusters = _fetch_accepted_clusters()
    if not clusters:
        logger.info("Briefing: no accepted clusters to process")
        return

    logger.info("Generating briefs for %d clusters", len(clusters))

    supabase = get_client()
    briefed = 0
    failed = 0

    for cluster in clusters:
        cluster_id = cluster["cluster_id"]
        anchor_article_id = cluster.get("anchor_article_id")

        articles = _fetch_cluster_articles(cluster_id)
        if not articles:
            logger.warning("Cluster %s has no articles — skipping", cluster_id)
            continue

        # Split into anchor + supporting
        anchor = next(
            (a for a in articles if a["id"] == anchor_article_id),
            articles[0],  # fall back to first article if anchor not found
        )
        supporting = [a for a in articles if a["id"] != anchor["id"]]

        result = _generate_brief(anchor, supporting, _CURVE_TOV, _BRIEF_INSTRUCTIONS)

        if result is None:
            failed += 1
            continue

        name, brief = result
        supabase.table(CLUSTERS_TABLE).update({
            "name": name,
            "brief": brief,
            "cluster_status": "briefed",
            "briefed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("cluster_id", cluster_id).execute()

        briefed += 1
        logger.debug("Cluster %s — brief generated (%d chars)", cluster_id, len(brief))

    logger.info(
        "Briefing complete — %d briefed, %d failed",
        briefed, failed,
    )
