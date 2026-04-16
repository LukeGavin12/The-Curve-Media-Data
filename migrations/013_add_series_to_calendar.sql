ALTER TABLE content_calendar_items
  ADD COLUMN series_id uuid,
  ADD COLUMN recurrence text CHECK (recurrence IN ('weekly', 'fortnightly', 'monthly'));

-- Prevents duplicate dates within the same series
CREATE UNIQUE INDEX content_calendar_items_series_date_idx
  ON content_calendar_items (series_id, publish_date)
  WHERE series_id IS NOT NULL;
