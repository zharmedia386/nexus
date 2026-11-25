CREATE TABLE IF NOT EXISTS community_summaries (
  tenant_id text NOT NULL REFERENCES tenants (id),
  community_id text NOT NULL,
  evidence_sha256 text NOT NULL,
  prompt_version text NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, community_id)
);
