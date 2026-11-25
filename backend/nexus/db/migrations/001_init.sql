CREATE TABLE IF NOT EXISTS tenants (
  id text PRIMARY KEY
);

INSERT INTO tenants (id) VALUES ('demo') ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS documents (
  id text NOT NULL,
  tenant_id text NOT NULL REFERENCES tenants (id),
  title text NOT NULL,
  doc_type text NOT NULL,
  lang text NOT NULL,
  year int NOT NULL,
  content text NOT NULL,
  sha256 text NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'ingested', 'failed')),
  error text,
  PRIMARY KEY (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS chunks (
  id text NOT NULL,
  tenant_id text NOT NULL,
  doc_id text NOT NULL,
  ordinal int NOT NULL,
  start_char int NOT NULL,
  end_char int NOT NULL,
  text text NOT NULL,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, doc_id) REFERENCES documents (tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (tenant_id, doc_id, ordinal);

CREATE TABLE IF NOT EXISTS eval_runs (
  id uuid PRIMARY KEY,
  tenant_id text NOT NULL REFERENCES tenants (id),
  created_at timestamptz NOT NULL DEFAULT now(),
  config jsonb NOT NULL
);

-- tenant is derived via run_id -> eval_runs.tenant_id
CREATE TABLE IF NOT EXISTS eval_results (
  run_id uuid NOT NULL REFERENCES eval_runs (id),
  question_id text NOT NULL,
  mode text NOT NULL,
  metrics jsonb NOT NULL,
  answer jsonb NOT NULL,
  PRIMARY KEY (run_id, question_id, mode)
);
