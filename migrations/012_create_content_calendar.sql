CREATE TABLE content_calendar_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  publish_date date NOT NULL,
  content_type text NOT NULL CHECK (content_type IN ('newsletter', 'podcast', 'substack')),
  title text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'published')),
  brief_ids text[] NOT NULL DEFAULT '{}',
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX content_calendar_items_publish_date_idx ON content_calendar_items (publish_date);
