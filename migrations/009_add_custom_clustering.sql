-- Adds cluster_type (auto/custom) to story_clusters.
-- Adds custom_cluster_prompt to pipeline_settings.
-- source_cluster_ids records which auto clusters were merged into a custom one.

alter table story_clusters
  add column if not exists cluster_type text not null default 'auto'
    check (cluster_type in ('auto', 'custom')),
  add column if not exists source_cluster_ids text[];

update story_clusters set cluster_type = 'auto' where cluster_type is null;

alter table pipeline_settings
  add column if not exists custom_cluster_prompt text not null default '';

update pipeline_settings
set custom_cluster_prompt = $PROMPT$You are an editorial assistant for Curve Media.

Review today's accepted news stories listed below. Identify any stories that belong together as a single roundup piece — covering the same theme from different angles or reporting on multiple similar events.

Good candidates:
- Multiple IPO announcements (different companies, same market theme)
- Multiple central bank rate decisions
- Multiple redundancy or job cut announcements
- Multiple stories covering the same policy area from different angles

Rules:
- Only group stories that genuinely belong together editorially
- A group must contain at least 2 stories
- Do not group stories that are already about the same single event
- Leave standalone stories alone — they have already been briefed individually

For each group, return:
- name: a short editorial title for the roundup (e.g. "IPO Roundup", "Central Bank Decisions")
- cluster_ids: array of cluster_id values from the stories below
- brief: a roundup brief in Curve's voice (150–250 words, plain text, no markdown)

Return a JSON array only. If nothing should be grouped, return [].
$PROMPT$
where id = 1;
