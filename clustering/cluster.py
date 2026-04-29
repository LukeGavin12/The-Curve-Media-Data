"""
Clustering — two Claude calls, one DB write.

Call 1 (week continuity): assign today's articles to ongoing stories from earlier this week.
Call 2 (new stories): group remaining articles into new named clusters.
Unplaced articles become singletons.
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
- Do NOT force groupings — if an article genuinely stands alone, leave it out
- Do NOT group articles just because they are in the same industry
- A cluster needs at least 2 articles
- Name each cluster with a short punchy headline (3–7 words, no filler)
- Description: one sentence (~10 words) summarising what the story is about

Return a JSON array of clusters only — empty array if nothing should be grouped.
Articles not included will be kept as individual stories.
Return a JSON array only: [{"name": "...", "description": "...", "article_ids": [...]}]"""


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


def _fetch_included_articles(run_date: str) -> list[dict]:
    client = get_client()
    resp = (
        client.table(TABLE)
        .select("id, title, summary")
        .eq("status", "included")
        .gte("fetched_at", f"{run_date}T00:00:00.000Z")
        .lte("fetched_at", f"{run_date}T23:59:59.999Z")
        .execute()
    )
    return resp.data or []


def _call_week_continuity(articles: list[dict], week_names: list[str]) -> dict[str, list[str]]:
    """
    Call 1: assign articles to ongoing week stories.
    Returns {week_name: [article_ids]}.
    Only returns matches — articles not mentioned are not continuing any week story.
    """
    article_lines = "\n".join(
        f'id: {a["id"]} | {a["title"]} — {(a.get("summary") or "").strip()}'
        for a in articles
    )
    names_block = "\n".join(f"  - {n}" for n in week_names)

    prompt = "\n".join([
        "You are an editorial assistant for Curve Media.",
        "These stories have been running earlier this week:",
        "",
        names_block,
        "",
        "Today's articles:",
        "",
        article_lines,
        "",
        "For each article that clearly continues one of this week's ongoing stories, assign it.",
        "Only assign if the article is genuinely reporting on the same ongoing narrative — not just the same broad topic.",
        "Articles not mentioned will be treated as new stories.",
        "",
        'Return JSON only — an array: [{"name": "<exact story name from the list above>", "description": "<10 words summarising the story>", "article_ids": [...]}]',
        "Return an empty array if nothing clearly continues a weekly story.",
    ])

    ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        msg = ai.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start = raw.find("[")
        if start == -1:
            return {}
        data = json.loads(raw[start:])
        week_name_set = set(week_names)
        result: dict[str, tuple[list[str], str]] = {}
        for item in data:
            name = (item.get("name") or "").strip()
            description = (item.get("description") or "").strip()
            ids = item.get("article_ids") or []
            if name in week_name_set and ids:
                result[name] = (ids, description)
        return result
    except Exception as exc:
        logger.warning("Week continuity call failed: %s", exc)
        return {}


def _call_new_clustering(articles: list[dict], system_prompt: str) -> list[dict]:
    """
    Call 2: group remaining articles into new named clusters.
    Returns [{name, description, article_ids}] — only multi-article groups.
    Articles not mentioned become singletons.
    """
    article_lines = "\n".join(
        f'id: {a["id"]} | {a["title"]} — {(a.get("summary") or "").strip()}'
        for a in articles
    )

    ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        msg = ai.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": article_lines}],
        )
        raw = msg.content[0].text.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start = raw.find("[")
        if start == -1:
            return []
        return json.loads(raw[start:])
    except Exception as exc:
        logger.warning("New clustering call failed: %s", exc)
        return []


def run_clustering(run_date: str | None = None) -> None:
    target_date = run_date or (date.today() - timedelta(days=1)).isoformat()
    logger.info("Clustering started for %s", target_date)

    settings = get_pipeline_settings()
    cluster_prompt = (settings.get("custom_cluster_prompt") or "").strip() or DEFAULT_CLUSTER_PROMPT

    articles = _fetch_included_articles(target_date)
    if not articles:
        logger.info("Clustering: no included articles to process")
        return

    logger.info("Clustering %d articles", len(articles))
    articles_by_id = {a["id"]: a for a in articles}
    assigned_ids: set[str] = set()

    # (name, article_ids, description, is_week_continuation)
    final_clusters: list[tuple[str, list[str], str, bool]] = []

    # ── Call 1: week continuity ──────────────────────────────────────────────
    week_names = _fetch_week_names(target_date)
    if week_names:
        logger.info("Checking %d articles against %d week stories", len(articles), len(week_names))
        week_assignments = _call_week_continuity(articles, week_names)
        for name, (ids, description) in week_assignments.items():
            valid_ids = [i for i in ids if i in articles_by_id]
            if valid_ids:
                final_clusters.append((name, valid_ids, description, True))
                assigned_ids.update(valid_ids)
        logger.info(
            "Week continuity: %d articles → %d ongoing stories",
            sum(len(ids) for ids, _ in week_assignments.values()),
            len(week_assignments),
        )
    else:
        logger.info("No earlier stories this week — skipping week continuity pass")

    # ── Call 2: new clustering ───────────────────────────────────────────────
    remaining = [a for a in articles if a["id"] not in assigned_ids]
    if remaining:
        logger.info("New clustering: grouping %d remaining articles", len(remaining))
        new_groups = _call_new_clustering(remaining, cluster_prompt)
        for group in new_groups:
            name = (group.get("name") or "").strip()
            description = (group.get("description") or "").strip()
            ids = [
                i for i in (group.get("article_ids") or [])
                if i in articles_by_id and i not in assigned_ids
            ]
            if name and len(ids) >= 2:
                final_clusters.append((name, ids, description, False))
                assigned_ids.update(ids)

    singletons = [a for a in articles if a["id"] not in assigned_ids]

    # ── DB write ─────────────────────────────────────────────────────────────
    supabase = get_client()

    for name, ids, description, is_continuation in final_clusters:
        cluster_id = str(uuid.uuid4())
        weekly_story = name.strip().lower() if is_continuation else None

        supabase.table(CLUSTERS_TABLE).insert({
            "cluster_id":     cluster_id,
            "date":           target_date,
            "name":           name,
            "description":    description or None,
            "weekly_story":   weekly_story,
            "article_count":  len(ids),
            "cluster_status": "pending",
        }).execute()
        supabase.table(TABLE).update({"cluster_id": cluster_id}).in_("id", ids).execute()

        if weekly_story:
            supabase.table(CLUSTERS_TABLE)\
                .update({"weekly_story": weekly_story})\
                .eq("name", name)\
                .is_("weekly_story", "null")\
                .execute()

    for a in singletons:
        cluster_id = str(uuid.uuid4())
        supabase.table(CLUSTERS_TABLE).insert({
            "cluster_id":     cluster_id,
            "date":           target_date,
            "name":           a.get("title", ""),
            "article_count":  1,
            "cluster_status": "pending",
        }).execute()
        supabase.table(TABLE).update({"cluster_id": cluster_id}).eq("id", a["id"]).execute()

    logger.info(
        "Clustering complete — %d articles → %d clusters (%d multi, %d singletons)",
        len(articles),
        len(final_clusters) + len(singletons),
        len(final_clusters),
        len(singletons),
    )
