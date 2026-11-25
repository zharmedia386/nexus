CREATE TABLE IF NOT EXISTS adjudications (
  tenant_id text NOT NULL REFERENCES tenants (id),
  pair_key text NOT NULL,
  same boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, pair_key)
);
