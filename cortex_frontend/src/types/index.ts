export interface PullRequest {
  id: string;
  github_pr_number: number;
  title: string;
  author: string;
  author_avatar_url: string;
  source_branch: string;
  target_branch: string;
  state: string;
  html_url: string;
  additions: number;
  deletions: number;
  changed_files: number;
  qa_status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  owner: string;
  repo_name: string;
  fetched_at: string | null;
}

export interface QAExecution {
  id: string;
  scan_id: string;
  repository_url: string;
  branch: string;
  commit_sha: string;
  tiers: string;
  execution_type: string;
  trigger: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  finding_count: number;
  severity_counts: Record<string, number> | null;
  quality_gate_status: string;
  duration_seconds: number;
  cost_usd: number;
  report_json_path: string;
  report_pdf_path: string;
  executive_json_path: string;
  executive_pdf_path: string;
  execution_log: string;
  error_message: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
}

export interface QAFinding {
  id: string;
  finding_id: string;
  source: string;
  tier: number;
  category: string;
  severity: string;
  confidence: string;
  file_path: string;
  start_line: number;
  end_line: number;
  title: string;
  explanation: string;
  recommendation: string;
  cwe: string | null;
  validation_status: string;
  linear_task_id: string | null;
}

export interface AppSettings {
  features: {
    github: boolean;
    linear: boolean;
    automation: boolean;
    analytics: boolean;
  };
  items: Array<{
    key: string;
    value: string;
    category: string;
    description: string;
  }>;
}
