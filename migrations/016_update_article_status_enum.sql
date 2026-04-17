-- Add 'included' and 'excluded' to article_status enum.
-- These replace 'assessing' (pass) and 'rejected' (fail) from the filtering stage.
-- Existing values are retained so historic data is not broken.

ALTER TYPE article_status ADD VALUE IF NOT EXISTS 'included';
ALTER TYPE article_status ADD VALUE IF NOT EXISTS 'excluded';
