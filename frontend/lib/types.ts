// Hand-mirrored from backend Pydantic models / dataclasses; keep in sync with backend/nexus.

export type Mode = "rag" | "hybrid" | "graph_local" | "graph_global" | "auto";

export type EntityType = "Company" | "Person" | "Group" | "Sector" | "Location";

export type RelType =
  | "FOUNDED"
  | "SERVES_AS"
  | "OWNS_STAKE"
  | "SUBSIDIARY_OF"
  | "INVESTED_IN"
  | "PARTNERS_WITH"
  | "FAMILY_OF"
  | "MEMBER_OF_GROUP"
  | "IN_SECTOR"
  | "HEADQUARTERED_IN";

export type QueryRequest = {
  question: string;
  mode: Mode;
  verify?: boolean;
};

export type Hit = {
  chunk_id: string;
  doc_id: string;
  text: string;
  score: number;
};

export type Claim = {
  text: string;
  chunk_ids: string[];
  supported: boolean | null;
};

export type PathHop = {
  src_id: string;
  src_name: string;
  rel_type: string;
  dst_id: string;
  dst_name: string;
  chunk_ids: string[];
  quotes: string[];
  doc_ids: string[];
  // False when the stored edge points dst -> src (against the walk).
  forward: boolean;
};

export type GraphPath = {
  node_ids: string[];
  node_names: string[];
  rel_types: string[];
  chunk_ids: string[];
  hops: PathHop[];
};

export type Answer = {
  text: string;
  citations: string[];
  invalid_citations: string[];
  hits: Hit[];
  abstained: boolean;
  mode: Mode;
  latency_ms: number;
  claims: Claim[];
  graph_paths: GraphPath[];
  communities: string[];
  routed_mode: Mode | null;
  llm_calls: number;
  verify_ms: number;
  verify_calls: number;
};

export type DocumentRow = {
  id: string;
  title: string;
  doc_type: string;
  lang: string;
  year: number;
  content: string;
  sha256: string;
  status: "pending" | "ingested" | "failed";
  error: string | null;
};

export type ChunkRow = {
  id: string;
  doc_id: string;
  ordinal: number;
  start_char: number;
  end_char: number;
  text: string;
};

export type EntityNode = {
  id: string;
  name: string;
  type: EntityType | null;
  aliases: string[];
};

export type EntityEdge = {
  type: RelType;
  outgoing: boolean;
  role: string | null;
  relation: string | null;
  pct: number | null;
  since: number | null;
  until: number | null;
  other_id: string;
  other_name: string;
  other_type: EntityType | null;
  chunk_ids: string[];
  quotes: string[];
};

export type EntityDetail = EntityNode & {
  chunk_ids: string[];
  edges: EntityEdge[];
};

export type EntitySearchResult = EntityNode & {
  match: "exact" | "prefix" | "substring";
};

export type Community = {
  id: string;
  level: number;
  size: number;
  title: string | null;
  summary: string | null;
  parent_id: string | null;
  member_ids: string[];
  member_names: string[];
  summary_chunk_ids: string[];
};

export type EvalCategory =
  | "all"
  | "single_hop"
  | "multi_hop_2"
  | "multi_hop_3"
  | "temporal"
  | "thematic"
  | "unanswerable";

export type EvalSummaryRow = {
  mode: Mode;
  category: EvalCategory;
  // null on unanswerable rows, which are scored by abstain_accuracy.
  answer_match: number | null;
  answer_match_ci_low: number | null;
  answer_match_ci_high: number | null;
  answer_precision: number;
  recall_at_k: number;
  citation_precision: number;
  unsupported_claim_rate: number;
  abstain_accuracy: number;
  p50_ms: number;
  p95_ms: number;
  mean_llm_calls: number;
  mean_verify_calls: number;
  mean_verify_ms: number;
  n: number;
  n_errors: number;
};

export type EvalDiff = {
  mode: Mode;
  category: EvalCategory;
  n: number;
  mean_diff: number;
  ci_low: number;
  ci_high: number;
  significant: boolean;
};

export type PrfScore = {
  precision: number;
  recall: number;
  f1: number;
  support: number;
};

export type JudgeWinRate = {
  a_wins: number;
  b_wins: number;
  ties: number;
  n: number;
  errors: number;
  a_win_rate: number;
  b_win_rate: number;
};

export type EvalJudge = {
  mode_a: Mode;
  mode_b: Mode;
  categories: EvalCategory[];
  judge_prompt_version: number;
  win_rates: Record<string, JudgeWinRate>;
  mean_chars: Partial<Record<Mode, number>>;
};

export type EvalReport = {
  run_id: string;
  rescored: boolean;
  claim_split_version: string;
  models: Record<string, string | number>;
  versions: Record<string, string | number | null>;
  summary: EvalSummaryRow[];
  diffs: EvalDiff[];
  significant_categories: Partial<Record<Mode, EvalCategory[]>>;
  answerable: number;
  unanswerable: number;
  routes: Partial<Record<Mode, number>>;
  claims: Partial<Record<Mode, Record<string, number>>>;
  awaiting_verify: number;
  // graph / judges are absent when that eval stage has not run.
  graph?: {
    timestamp: string;
    docs: number;
    entity_macro: PrfScore;
    entity_micro: PrfScore;
    relations: {
      macro: PrfScore;
      micro: PrfScore;
      temporal_accuracy: number;
      temporal_support: number;
      by_type: Record<string, PrfScore>;
    };
    er?: {
      precision: number;
      recall: number;
      f1: number;
      collision_merges: number;
      ticker_links: number;
      ticker_total: number;
    };
  };
  judges?: EvalJudge[];
  audit: {
    run: string;
    mode: Mode;
    category: EvalCategory;
    classes: Record<string, number>;
    n: number;
  };
  dataset: {
    seed: number;
    entities: Partial<Record<EntityType, number>>;
    edges: Partial<Record<RelType, number>>;
    docs: Record<string, Record<string, number>>;
    review_rows?: number;
    review_marked?: number;
  };
  examples: string[];
  example_counts: Record<string, number>;
  caveats?: string[];
};

export type GraphStats = {
  nodes: number;
  relationships: number;
  by_type: Partial<Record<EntityType, number>>;
  top: { id: string; name: string; type: EntityType | null; degree: number }[];
};

export type Health = Record<string, "ok" | "down">;
