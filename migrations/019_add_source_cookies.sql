ALTER TABLE sources
  ADD COLUMN IF NOT EXISTS cookies text;

COMMENT ON COLUMN sources.cookies IS
  'Raw Cookie header string for paywalled sources (e.g. "SID=abc; FTSession=xyz").
   Paste from DevTools → Network → any request → Request Headers → Cookie.
   Update via the admin UI when cookies expire. NULL = no auth needed.';
