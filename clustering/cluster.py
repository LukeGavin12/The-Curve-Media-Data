"""
Stage 3 — Claude Clustering.

Groups filtered articles editorially using Claude. Multi-article clusters
get a Claude-generated name; single articles keep their original title.

Replaces the previous Voyage AI vector clustering + hybrid Claude pass.
"""

import json
import logging
import uuid
from datetime import date, timedelta

import anthropic

from config import ANTHROPIC_API_KEY
from ingestion.storage import get_client, get_pipeline_settings, TABLE

logger = logging.getLogger(__name__)

CLUSTERS_TABLE = "story_clusters"
MODEL = "claude-sonnet-4-6"

DEFAULT_CLUSTER_PROMPT = """You are an editorial assistant for Curve Media, clustering today's financial news articles into distinct stories.

Group articles that are reporting on the same underlying story or feeding into the same broader narrative. Think editorially — two articles belong together if a reader would expect to read them as part of the same story, even if the headlines look different.

Rules:
- Group articles covering the same story or closely related developments
- Cluster along broad themes where multiple articles clearly feed the same narrative
- Do NOT force groupings — if an article genuinely stands alone, leave it as a single
- Do NOT group articles just because they are in the same industry
- A cluster needs at least 2 articles

Return a JSON array of clusters only (do not include singles). For each cluster:
- name: short punchy headline for the group (3–7 words, no filler)
- article_ids: array of article id values

Any articles not in a cluster will be kept as singles automatically.
Return a JSON array only — empty array if nothing should be grouped."""


def _fetch_assessing_articles(run_date: str) -> list[dict]:
    client = get_client()
    resp = (
        client.table(TABLE)
        .select("id, guid, title, summary, published_at")
        .eq("status", "assessing")
        .gte("fetched_at", f"{run_date}T00:00:00.000Z")
        .lte("fetched_at", f"{run_date}T23:59:59.999Z")
        .execute()
    )
    return resp.data or []


def _call_claude(articles: list[dict], system_prompt: str) -> list[dict]:
    """Send articles to Claude, get back list of {name, article_ids}."""
    lines = []
    for a in articles:
        lines.append(f'id: {a["id"]}')
        lines.append(f'title: {a["title"]}')
        summary = (a.get("summary") or "").strip()
        if summary:
            lines.append(f'summary: {summary}')
        lines.append("")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": "\n".join(lines)}],
    )
    raw = msg.content[0].text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def run_clustering(run_date: str | None = None) -> None:
    target_date = run_date or (date.today() - timedelta(days=1)).isoformat()
    logger.info("Claude clustering started for %s", target_date)

    settings = get_pipeline_settings()
    system_prompt = (settings.get("custom_cluster_prompt") or "").strip() or DEFAULT_CLUSTER_PROMPT

    articles = _fetch_assessing_articles(target_date)
    if not articles:
        logger.info("Clustering: no assessing articles to process")
        return

    logger.info("Clustering %d articles with Claude", len(articles))
    articles_by_id = {a["id"]: a for a in articles}
    supabase = get_client()
    assigned_ids: set[str] = set()
    multi_count = 0

    try:
        clusters = _call_claude(articles, system_prompt)
    except Exception as exc:
        logger.error("Claude clustering failed: %s", exc)
        return

    for group in clusters:
        name = (group.get("name") or "").strip()
        article_ids = [aid for aid in (group.get("article_ids") or []) if aid in articles_by_id]

        if not name or len(article_ids) < 2:
            continue

        cluster_id = str(uuid.uuid4())
        cluster_articles = [articles_by_id[aid] for aid in article_ids]
        anchor = min(cluster_articles, key=lambda a: a.get("published_at") or "9999-12-31")

        supabase.table(CLUSTERS_TABLE).insert({
            "cluster_id":        cluster_id,
            "date":              target_date,
            "name":              name,
            "anchor_article_id": anchor["id"],
            "article_count":     len(article_ids),
            "cluster_status":    "pending",
        }).execute()

        supabase.table(TABLE).update({"cluster_id": cluster_id}).in_("id", article_ids).execute()

        assigned_ids.update(article_ids)
        multi_count += 1

    # Singles — keep original title
    singles = [a for a in articles if a["id"] not in assigned_ids]
    for a in singles:
        cluster_id = str(uuid.uuid4())
        supabase.table(CLUSTERS_TABLE).insert({
            "cluster_id":        cluster_id,
            "date":              target_date,
            "name":              a.get("title", ""),
            "anchor_article_id": a["id"],
            "article_count":     1,
            "cluster_status":    "pending",
        }).execute()
        supabase.table(TABLE).update({"cluster_id": cluster_id}).eq("id", a["id"]).execute()

    logger.info(
        "Clustering complete — %d articles → %d multi-article clusters, %d singles",
        len(articles), multi_count, len(singles),
    )
