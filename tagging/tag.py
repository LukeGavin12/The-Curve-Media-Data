"""
Stage 4b — Tagging.

Assigns topic and geographic tags to accepted clusters using a focused
Claude call. Runs immediately after scoring on the same date.

Only clusters at or above score_threshold are tagged.
"""

import json
import logging
from typing import Any

import anthropic

from config import ANTHROPIC_API_KEY
from ingestion.storage import get_client, get_pipeline_settings, TABLE

logger = logging.getLogger(__name__)

CLUSTERS_TABLE = "story_clusters"
TAGGING_MODEL = "claude-haiku-4-5-20251001"


def _fetch_accepted_clusters(run_date: str, score_threshold: float) -> list[dict[str, Any]]:
    client = get_client()
    response = (
        client.table(CLUSTERS_TABLE)
        .select("id, cluster_id")
        .eq("date", run_date)
        .eq("cluster_status", "accepted")
        .gte("relevance_score", score_threshold)
        .execute()
    )
    return response.data or []


def _fetch_articles_for_clusters(cluster_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    from collections import defaultdict
    client = get_client()
    grouped: dict[str, list] = defaultdict(list)
    for i in range(0, len(cluster_ids), 50):
        chunk = cluster_ids[i: i + 50]
        response = (
            client.table(TABLE)
            .select("cluster_id, title, summary")
            .in_("cluster_id", chunk)
            .execute()
        )
        for article in (response.data or []):
            grouped[article["cluster_id"]].append(article)
    return grouped


def _build_prompt(clusters: list[dict], articles_by_cluster: dict,
                  available_tags: list[str], available_geo_tags: list[str]) -> str:
    parts = [
        "For each story cluster below, assign the most relevant topic tags and geographic tags.",
        "Return a JSON array with one object per cluster in the same order.",
        'Each object must have: "index" (int), "tags" (array of 0-3 topic tags), "geo_tags" (array of geographic tags).',
        "Only use tags from the provided lists. Use empty arrays if none apply.",
        f"Available topic tags: {', '.join(available_tags)}",
        f"Available geographic tags: {', '.join(available_geo_tags)}",
        "Return only the JSON array. No preamble or markdown fences.",
        "",
    ]
    for i, cluster in enumerate(clusters, 1):
        articles = articles_by_cluster.get(cluster["cluster_id"], [])
        parts.append(f"--- Cluster {i} ---")
        for article in articles:
            parts.append(f"{article.get('title', '')}: {article.get('summary', '')}")
        parts.append("")
    return "\n".join(parts)


def _call_claude(clusters: list[dict], articles_by_cluster: dict,
                 available_tags: list[str], available_geo_tags: list[str]) -> dict[str, tuple[list, list]]:
    prompt = _build_prompt(clusters, articles_by_cluster, available_tags, available_geo_tags)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        message = client.messages.create(
            model=TAGGING_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        start = raw.find("[")
        if start != -1:
            raw = raw[start:].removesuffix("```").strip()
        data = json.loads(raw)

        tag_lookup = {t.lower(): t for t in available_tags}
        geo_lookup = {t.lower(): t for t in available_geo_tags}

        results: dict[str, tuple[list, list]] = {}
        for item in data:
            idx = int(item["index"]) - 1
            if 0 <= idx < len(clusters):
                cluster_id = clusters[idx]["cluster_id"]
                tags = [tag_lookup[t.lower()] for t in (item.get("tags") or []) if t.lower() in tag_lookup]
                geo_tags = [geo_lookup[t.lower()] for t in (item.get("geo_tags") or []) if t.lower() in geo_lookup]
                results[cluster_id] = (tags, geo_tags)

        return results

    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        logger.warning("Could not parse tagging response: %s", exc)
    except Exception as exc:
        logger.warning("Tagging API error: %s", exc)

    return {}


def run_tagging(run_date: str | None = None) -> None:
    from datetime import date, timedelta
    target_date = run_date or (date.today() - timedelta(days=1)).isoformat()
    logger.info("Tagging started for %s", target_date)

    settings = get_pipeline_settings()
    available_tags = settings.get("available_tags") or []
    available_geo_tags = settings.get("available_geo_tags") or []
    score_threshold = float(settings.get("score_threshold") or 0.4)

    if not available_tags and not available_geo_tags:
        logger.info("Tagging: no tags configured in pipeline_settings — skipping")
        return

    clusters = _fetch_accepted_clusters(target_date, score_threshold)
    if not clusters:
        logger.info("Tagging: no accepted clusters to tag for %s", target_date)
        return

    logger.info("Tagging %d clusters for %s", len(clusters), target_date)

    cluster_ids = [c["cluster_id"] for c in clusters]
    articles_by_cluster = _fetch_articles_for_clusters(cluster_ids)

    results = _call_claude(clusters, articles_by_cluster, available_tags, available_geo_tags)

    if not results:
        logger.warning("Tagging: no results returned — clusters left untagged")
        return

    supabase = get_client()
    for cluster_id, (tags, geo_tags) in results.items():
        supabase.table(CLUSTERS_TABLE).update({
            "tags": tags,
            "geo_tags": geo_tags,
        }).eq("cluster_id", cluster_id).execute()

    logger.info("Tagging complete — %d clusters tagged", len(results))
