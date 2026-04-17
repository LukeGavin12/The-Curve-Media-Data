ALTER TABLE content_calendar_items
  DROP CONSTRAINT IF EXISTS content_calendar_items_content_type_check;

ALTER TABLE content_calendar_items
  ADD CONSTRAINT content_calendar_items_content_type_check
  CHECK (content_type IN ('newsletter', 'podcast', 'substack', 'daily_briefing'));
