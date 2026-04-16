"""
Stage 3 — Clustering.

Groups articles at status='assessing' into story clusters using vector embeddings
and cosine similarity. One cluster per distinct story; each article gets a
cluster_id written back to news_articles.

Process:
  1. Fetch all status='assessing' articles
  2. Embed each article (title + summary) via Voyage AI voyage-finance-2
  3. Build pairwise cosine similarity matrix
  4. Assign clusters via union-find on pairs with similarity >= SIMILARITY_THRESHOLD
  5. Insert one row per cluster into story_clusters
  6. Write cluster_id back to each article (status stays 'assessing' — Stage 4 decides accept/reject)
"""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np
import voyageai

from pipeline.config import VOYAGE_API_KEY
from pipeline.ingestion.storage import get_client, get_pipeline_settings, TABLE

logger = logging.getLogger(__name__)

CLUSTERS_TABLE = "story_clusters"
VOYAGE_MODEL = "voyage-3"
VOYAGE_BATCH_SIZE = 128   # Voyage API max per request

REFINEMENT_THRESHOLDS = [0.70, 0.75, 0.80]   # applied iteratively to oversized clusters
REFINEMENT_MAX_SIZE = 5                        # re-cluster any group larger than this


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_assessing_articles(run_date: str) -> list[dict[str, Any]]:
    """Return articles at status='assessing' fetched on run_date."""
    client = get_client()
    response = (
        client.table(TABLE)
        .select("id, guid, title, summary, published_at")
        .eq("status", "assessing")
        .gte("fetched_at", f"{run_date}T00:00:00.000Z")
        .lte("fetched_at", f"{run_date}T23:59:59.999Z")
        .execute()
    )
    return response.data or []


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def _generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Embed texts in batches via Voyage AI.
    Returns a list of float vectors, one per input text.
    """
    vo = voyageai.Client(api_key=VOYAGE_API_KEY)
    embeddings: list[list[float]] = []
    batches = [texts[i: i + VOYAGE_BATCH_SIZE] for i in range(0, len(texts), VOYAGE_BATCH_SIZE)]

    for idx, batch in enumerate(batches):
        result = vo.embed(batch, model=VOYAGE_MODEL, input_type="document")
        embeddings.extend(result.embeddings)
        logger.info("Embeddings: batch %d/%d done (%d texts)", idx + 1, len(batches), len(batch))

    return embeddings


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def _cosine_similarity_matrix(embeddings: list[list[float]]) -> np.ndarray:
    mat = np.array(embeddings, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)   # avoid division by zero
    normalised = mat / norms
    return normalised @ normalised.T


def _assign_clusters(embeddings: list[list[float]], threshold: float) -> list[int]:
    """
    Returns a root index per article. Articles sharing a root belong to the same cluster.
    Uses union-find: any pair with cosine similarity >= threshold is merged.
    """
    n = len(embeddings)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]   # path compression
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    sim = _cosine_similarity_matrix(embeddings)
    for i in range(n):
        for j in range(i + 1, n):
            if float(sim[i, j]) >= threshold:
                union(i, j)

    return [find(i) for i in range(n)]


def _multi_pass_cluster(
    embeddings: list[list[float]],
    initial_threshold: float,
    refinement_thresholds: list[float],
    max_size: int,
) -> dict[int, list[int]]:
    """
    Clusters all articles with initial_threshold, then iteratively re-clusters
    any group larger than max_size with progressively stricter thresholds.
    Returns a mapping of root index → list of article indices.
    """
    roots = _assign_clusters(embeddings, initial_threshold)

    root_to_indices: dict[int, list[int]] = defaultdict(list)
    for idx, root in enumerate(roots):
        root_to_indices[root].append(idx)

    for threshold in refinement_thresholds:
        oversized = {r: idxs for r, idxs in root_to_indices.items() if len(idxs) > max_size}
        if not oversized:
            logger.info("Multi-pass: no oversized clusters — stopping early")
            break

        logger.info(
            "Multi-pass threshold=%.2f: re-clustering %d oversized group(s)",
            threshold, len(oversized),
        )

        # Keep small clusters unchanged, re-cluster oversized ones
        next_root_to_indices: dict[int, list[int]] = {
            r: idxs for r, idxs in root_to_indices.items() if len(idxs) <= max_size
        }

        for _, indices in oversized.items():
            sub_embeddings = [embeddings[i] for i in indices]
            sub_roots = _assign_clusters(sub_embeddings, threshold)

            sub_root_to_orig: dict[int, list[int]] = defaultdict(list)
            for sub_idx, sub_root in enumerate(sub_roots):
                sub_root_to_orig[sub_root].append(indices[sub_idx])

            for orig_indices in sub_root_to_orig.values():
                new_root = orig_indices[0]
                next_root_to_indices[new_root] = orig_indices

        root_to_indices = next_root_to_indices

    return root_to_indices


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_clustering(run_date: str | None = None) -> None:
    """
    Stage 3 clustering. Run after filtering, before scoring.

    Writes:
      - story_clusters rows (one per cluster, status='pending')
      - news_articles.cluster_id for every processed article
    Article status stays 'assessing' — Stage 4 sets it to accepted/rejected.
    """
    from datetime import date as _date, timedelta
    target_date = run_date or (_date.today() - timedelta(days=1)).isoformat()
    logger.info("Clustering started for %s", target_date)

    SIMILARITY_THRESHOLD = float(get_pipeline_settings()["similarity_threshold"])

    articles = _fetch_assessing_articles(target_date)
    if not articles:
        logger.info("Clustering: no assessing articles to process")
        return

    logger.info("Clustering %d articles", len(articles))

    # Build embedding input: title + summary
    texts = [
        f"{a['title']} {a.get('summary') or ''}".strip()
        for a in articles
    ]

    embeddings = _generate_embeddings(texts)
    logger.info("Embeddings generated for %d articles", len(embeddings))

    root_to_indices = _multi_pass_cluster(
        embeddings, SIMILARITY_THRESHOLD, REFINEMENT_THRESHOLDS, REFINEMENT_MAX_SIZE
    )

    supabase = get_client()

    singleton_count = 0
    for root, indices in root_to_indices.items():
        cluster_id = str(uuid.uuid4())
        cluster_articles = [articles[i] for i in indices]

        # Anchor = article with the earliest published_at (most timely source)
        anchor = min(
            cluster_articles,
            key=lambda a: a.get("published_at") or "9999-12-31",
        )

        # Write cluster record — name taken from anchor article title
        supabase.table(CLUSTERS_TABLE).insert({
            "cluster_id": cluster_id,
            "date": target_date,
            "name": anchor.get("title", ""),
            "anchor_article_id": anchor["id"],
            "article_count": len(cluster_articles),
            "cluster_status": "pending",
        }).execute()

        # Write cluster_id back to articles (status stays 'assessing')
        guids = [a["guid"] for a in cluster_articles]
        supabase.table(TABLE).update({"cluster_id": cluster_id}).in_("guid", guids).execute()

        if len(indices) == 1:
            singleton_count += 1

    cluster_count = len(root_to_indices)
    logger.info(
        "Clustering complete — %d articles → %d clusters (%d singletons, %d multi-article)",
        len(articles),
        cluster_count,
        singleton_count,
        cluster_count - singleton_count,
    )
