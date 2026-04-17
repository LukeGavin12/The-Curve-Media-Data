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
- tags: array of 0–3 relevant topic tags from the provided list (empty array if none fit)
- geo_tags: array of relevant geographic tags from the provided list (empty array if none fit)

Any articles not in a cluster will be kept as singles automatically.
Return a JSON array only — empty array if nothing should be grouped."""


def _get_monday(d: str) -> str:
    dt = date.fromisoformat(d)
    return (dt - timedelta(days=dt.weekday())).isoformat()


def _fetch_week_names(target_date: str) -> list[str]:
    """Return unique cluster names used earlier this week (Mon up to target_date)."""
    monday = _get_monday(target_date)
    if monday >= target_date:
        return []
    supabase = get_client()
    resp = (
        supabase.table(CLUSTERS_TABLE)
        .select("name")
        .gte("date", monday)
        .lt("date", target_date)
        .not_.is_("name", "null")
        .execute()
    )
    seen = set()
    names = []
    for r in (resp.data or []):
        name = (r.get("name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


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


def _build_system_prompt(base_prompt: str, week_names: list[str], available_tags: list[str], available_geo_tags: list[str]) -> str:
    prompt = base_prompt
    if week_names:
        names_block = "\n".join(f"  - {n}" for n in week_names)
        prompt += f"\n\nStory names already used this week — if a cluster is clearly the same ongoing story, reuse the exact name:\n{names_block}"
    if available_tags:
        prompt += f"\n\nAvailable topic tags: {', '.join(available_tags)}"
    if available_geo_tags:
        prompt += f"\nAvailable geographic tags: {', '.join(available_geo_tags)}"
    return prompt


def _call_claude(articles: list[dict], system_prompt: str) -> list[dict]:
    """Send articles to Claude, get back list of {name, article_ids}."""
    lines = []
    for a in articles:
        lines.append(f'id: {a["id"]} | {a["title"]}')

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": "\n".join(lines)}],
    )
    raw = msg.content[0].text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    if not raw:
        logger.warning("Claude returned empty response for clustering — treating as no clusters")
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Claude returned non-JSON for clustering (%.200s…): %s", raw, exc)
        return []


def run_clustering(run_date: str | None = None) -> None:
    target_date = run_date or (date.today() - timedelta(days=1)).isoformat()
    logger.info("Claude clustering started for %s", target_date)

    settings = get_pipeline_settings()
    base_prompt = (settings.get("custom_cluster_prompt") or "").strip() or DEFAULT_CLUSTER_PROMPT
    available_tags = settings.get("available_tags") or []
    available_geo_tags = settings.get("available_geo_tags") or []

    week_names = _fetch_week_names(target_date)
    logger.info("Found %d existing story names from earlier this week", len(week_names))
    system_prompt = _build_system_prompt(base_prompt, week_names, available_tags, available_geo_tags)

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

        tags = [t for t in (group.get("tags") or []) if t in available_tags]
        geo_tags = [t for t in (group.get("geo_tags") or []) if t in available_geo_tags]

        supabase.table(CLUSTERS_TABLE).insert({
            "cluster_id":        cluster_id,
            "date":              target_date,
            "name":              name,
            "anchor_article_id": anchor["id"],
            "article_count":     len(article_ids),
            "cluster_status":    "pending",
            "tags":              tags,
            "geo_tags":          geo_tags,
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
