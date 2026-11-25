CREATE TABLE IF NOT EXISTS extractions (
  tenant_id text NOT NULL,
  chunk_id text NOT NULL,
  content_sha256 text NOT NULL,
  prompt_version text NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, chunk_id),
  FOREIGN KEY (tenant_id, chunk_id) REFERENCES chunks (tenant_id, id) ON DELETE CASCADE
);
