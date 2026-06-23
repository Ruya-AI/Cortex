import { useEffect, useState, useCallback } from 'react';
import { fetchApi } from '../hooks/useApi';
import { PullRequest, QAExecution } from '../types';

interface Repository {
  id: string; owner: string; repo_name: string; full_name: string; description: string;
  default_branch: string; auto_fetch_prs: boolean; auto_qa_on_pr: boolean;
  qa_tiers: string; is_active: boolean;
}

interface Commit {
  sha: string; short_sha: string; message: string; author: string;
  author_login: string; author_avatar: string; date: string; html_url: string;
}

type TabKey = 'repositories' | 'pull_requests' | 'commits';

const TIER_OPTIONS = [
  { value: '1', label: 'Tier 1 (deterministic tools)' },
  { value: '1,2', label: 'Tier 1 + 2 (tools + agents)' },
  { value: '1,2,3', label: 'All tiers (tools + agents + cross-file)' },
];

const STATUS_CONFIG: Record<string, { bg: string; fg: string; dot: string; label: string }> = {
  running:   { bg: '#cfe2ff', fg: '#0d6efd', dot: '#0d6efd', label: 'Running' },
  pending:   { bg: '#cfe2ff', fg: '#0d6efd', dot: '#0d6efd', label: 'Pending' },
  completed: { bg: '#d1e7dd', fg: '#198754', dot: '#198754', label: 'Completed' },
  failed:    { bg: '#f8d7da', fg: '#dc3545', dot: '#dc3545', label: 'Failed' },
  not_started: { bg: '#e9ecef', fg: '#6c757d', dot: '#adb5bd', label: 'Not Started' },
  skipped:   { bg: '#e9ecef', fg: '#6c757d', dot: '#adb5bd', label: 'Skipped' },
};

const STATUS_FILTERS = [
  { key: '', label: 'All' },
  { key: 'running', label: 'Running' },
  { key: 'completed', label: 'Completed' },
  { key: 'failed', label: 'Failed' },
  { key: 'pending', label: 'Pending' },
];

function QAStatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.not_started;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      background: cfg.bg, color: cfg.fg,
      padding: '3px 10px', borderRadius: '12px',
      fontSize: '11px', fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      <span style={{
        width: '7px', height: '7px', borderRadius: '50%', background: cfg.dot,
        display: 'inline-block',
        animation: status === 'running' ? 'pulse 1.5s ease-in-out infinite' : 'none',
      }} />
      {cfg.label}
      <style>{`@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
    </span>
  );
}

const tabStyle = (active: boolean): React.CSSProperties => ({
  padding: '10px 24px', cursor: 'pointer', fontWeight: active ? 700 : 400,
  borderBottom: active ? '3px solid #0f3460' : '3px solid transparent',
  color: active ? '#0f3460' : '#666', fontSize: '14px', background: 'none', border: 'none',
});

const filterPill = (active: boolean): React.CSSProperties => ({
  padding: '4px 14px', borderRadius: '16px', fontSize: '12px', fontWeight: active ? 600 : 400,
  border: active ? '2px solid #0f3460' : '1px solid #ccc',
  background: active ? '#e8f0fe' : '#fff', color: active ? '#0f3460' : '#666',
  cursor: 'pointer',
});

export function QAExecutionPage() {
  const [tab, setTab] = useState<TabKey>('repositories');
  const [qaTiers, setQaTiers] = useState('1,2');
  const [historyKey, setHistoryKey] = useState(0);

  const onQATriggered = () => setHistoryKey(k => k + 1);

  return (
    <div>
      <h2 style={{ marginBottom: '20px' }}>QA Execution</h2>

      <div style={{ display: 'flex', borderBottom: '1px solid #dee2e6', marginBottom: '20px', gap: '4px' }}>
        {([['repositories', 'Repositories'], ['pull_requests', 'Pull Requests'], ['commits', 'Commits']] as const).map(([key, label]) => (
          <button key={key} style={tabStyle(tab === key)} onClick={() => setTab(key)}>{label}</button>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <label style={{ fontSize: '13px', fontWeight: 600, color: '#333' }}>QA Tiers:</label>
        <select value={qaTiers} onChange={e => setQaTiers(e.target.value)}
          style={{ padding: '6px 10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '13px' }}>
          {TIER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {tab === 'repositories' && <RepoTab tiers={qaTiers} onTriggered={onQATriggered} />}
      {tab === 'pull_requests' && <PRTab tiers={qaTiers} onTriggered={onQATriggered} />}
      {tab === 'commits' && <CommitTab tiers={qaTiers} onTriggered={onQATriggered} />}

      <ExecutionHistory
        key={historyKey}
        executionType={tab === 'pull_requests' ? 'pull_request' : tab === 'commits' ? 'commit' : 'repository'}
      />
    </div>
  );
}

function RepoTab({ tiers, onTriggered }: { tiers: string; onTriggered: () => void }) {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [executing, setExecuting] = useState(false);
  const [msg, setMsg] = useState('');
  const [repoStatuses, setRepoStatuses] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchApi<{ items: Repository[] }>('/api/github/repos')
      .then(d => setRepos(d.items.filter(r => r.is_active))).catch(() => {});
    fetchApi<{ items: QAExecution[] }>('/api/qa/executions?limit=50&type=repository')
      .then(d => {
        const map: Record<string, string> = {};
        for (const e of d.items) {
          const key = e.repository_url.replace(/\.git$/, '').split('/').slice(-2).join('/');
          if (!map[key]) map[key] = e.status;
        }
        setRepoStatuses(map);
      }).catch(() => {});
  }, []);

  const toggle = (id: string) => setSelected(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleAll = () => setSelected(selected.size === repos.length ? new Set() : new Set(repos.map(r => r.id)));

  const runQA = async () => {
    if (selected.size === 0) return;
    setExecuting(true); setMsg('');
    const sel = repos.filter(r => selected.has(r.id));
    let ok = 0;
    for (const repo of sel) {
      setMsg(`Running QA on ${repo.full_name} (${ok + 1}/${sel.length})...`);
      try {
        await fetchApi('/api/qa/execute', { method: 'POST', body: JSON.stringify({
          repository_url: `https://github.com/${repo.owner}/${repo.repo_name}.git`,
          branch: repo.default_branch, tiers: tiers.split(',').map(Number), execution_type: 'repository',
        })});
        ok++;
        setRepoStatuses(prev => ({ ...prev, [repo.full_name]: 'pending' }));
      } catch { /* skip */ }
    }
    setMsg(`QA triggered for ${ok}/${sel.length} repositories.`);
    setExecuting(false); setSelected(new Set());
    onTriggered();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{ fontSize: '13px', color: '#666' }}>{repos.length} repositories</span>
        <button onClick={runQA} disabled={selected.size === 0 || executing}
          style={{ padding: '8px 24px', background: selected.size > 0 && !executing ? '#0f3460' : '#ccc', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, fontSize: '13px', cursor: selected.size > 0 && !executing ? 'pointer' : 'default' }}>
          {executing ? 'Running...' : `Run QA (${selected.size} selected)`}
        </button>
      </div>
      {msg && <StatusMsg msg={msg} />}
      <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
              <th style={{ padding: '10px', width: '40px' }}>
                <input type="checkbox" checked={selected.size === repos.length && repos.length > 0} onChange={toggleAll} />
              </th>
              <th style={{ padding: '10px' }}>Repository</th>
              <th style={{ padding: '10px' }}>Description</th>
              <th style={{ padding: '10px' }}>Branch</th>
              <th style={{ padding: '10px' }}>QA Status</th>
            </tr>
          </thead>
          <tbody>
            {repos.map(r => (
              <tr key={r.id} onClick={() => toggle(r.id)} style={{ borderBottom: '1px solid #f0f0f0', background: selected.has(r.id) ? '#f0f7ff' : 'transparent', cursor: 'pointer' }}>
                <td style={{ padding: '10px' }} onClick={e => e.stopPropagation()}>
                  <input type="checkbox" checked={selected.has(r.id)} onChange={() => toggle(r.id)} />
                </td>
                <td style={{ padding: '10px', fontWeight: 600, color: '#0f3460' }}>{r.full_name}</td>
                <td style={{ padding: '10px', color: '#666', fontSize: '13px' }}>{r.description || '—'}</td>
                <td style={{ padding: '10px' }}><code style={{ background: '#f4f4f4', padding: '2px 6px', borderRadius: '3px', fontSize: '12px' }}>{r.default_branch}</code></td>
                <td style={{ padding: '10px' }}>
                  <QAStatusBadge status={repoStatuses[r.full_name] || 'not_started'} />
                </td>
              </tr>
            ))}
            {repos.length === 0 && <tr><td colSpan={5} style={{ padding: '20px', textAlign: 'center', color: '#999' }}>No repositories configured. Go to Admin to add.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PRTab({ tiers, onTriggered }: { tiers: string; onTriggered: () => void }) {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [prs, setPrs] = useState<PullRequest[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [fetching, setFetching] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    fetchApi<{ items: Repository[] }>('/api/github/repos').then(d => setRepos(d.items.filter(r => r.is_active))).catch(() => {});
    fetchApi<{ items: PullRequest[] }>('/api/pull-requests/').then(d => setPrs(d.items)).catch(() => {});
  }, []);

  const fetchAllPRs = async () => {
    setFetching(true); setMsg('');
    let created = 0, updated = 0, errors = 0;
    for (const repo of repos) {
      try {
        const r = await fetchApi<{ created: number; updated: number }>(`/api/github/repos/${repo.id}/fetch-prs`, { method: 'POST' });
        created += r.created; updated += r.updated;
      } catch { errors++; }
    }
    setMsg(`${created} new PRs, ${updated} updated${errors > 0 ? `, ${errors} errors` : ''}.`);
    fetchApi<{ items: PullRequest[] }>('/api/pull-requests/').then(d => setPrs(d.items)).catch(() => {});
    setFetching(false);
  };

  const toggle = (id: string) => setSelected(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const runQA = async () => {
    if (selected.size === 0) return;
    setExecuting(true); setMsg('');
    const sel = prs.filter(p => selected.has(p.id));
    let ok = 0;
    for (const pr of sel) {
      try {
        await fetchApi('/api/qa/execute', { method: 'POST', body: JSON.stringify({
          repository_url: `https://github.com/${pr.owner}/${pr.repo_name}.git`,
          branch: pr.source_branch, pr_number: pr.github_pr_number,
          tiers: tiers.split(',').map(Number), execution_type: 'pull_request',
        })});
        ok++;
      } catch { /* skip */ }
    }
    setMsg(`QA triggered for ${ok}/${sel.length} PRs.`);
    setExecuting(false); setSelected(new Set());
    onTriggered();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <button onClick={fetchAllPRs} disabled={fetching || repos.length === 0}
          style={{ padding: '8px 20px', background: !fetching && repos.length > 0 ? '#28a745' : '#ccc', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, fontSize: '13px', cursor: !fetching ? 'pointer' : 'default' }}>
          {fetching ? 'Fetching...' : 'Fetch PRs from GitHub'}
        </button>
        <button onClick={runQA} disabled={selected.size === 0 || executing}
          style={{ padding: '8px 24px', background: selected.size > 0 && !executing ? '#0f3460' : '#ccc', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, fontSize: '13px', cursor: selected.size > 0 && !executing ? 'pointer' : 'default' }}>
          {executing ? 'Running...' : `Run QA (${selected.size} selected)`}
        </button>
      </div>
      {msg && <StatusMsg msg={msg} />}
      <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
              <th style={{ padding: '10px', width: '40px' }}></th>
              <th style={{ padding: '10px' }}>PR</th>
              <th style={{ padding: '10px' }}>Title</th>
              <th style={{ padding: '10px' }}>Author</th>
              <th style={{ padding: '10px' }}>Branch</th>
              <th style={{ padding: '10px' }}>Repo</th>
              <th style={{ padding: '10px' }}>QA Status</th>
            </tr>
          </thead>
          <tbody>
            {prs.map(pr => (
              <tr key={pr.id} onClick={() => toggle(pr.id)} style={{ borderBottom: '1px solid #f0f0f0', background: selected.has(pr.id) ? '#f0f7ff' : 'transparent', cursor: 'pointer' }}>
                <td style={{ padding: '10px' }} onClick={e => e.stopPropagation()}>
                  <input type="checkbox" checked={selected.has(pr.id)} onChange={() => toggle(pr.id)} />
                </td>
                <td style={{ padding: '10px' }}>
                  <a href={pr.html_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} style={{ color: '#0f3460', fontWeight: 600, textDecoration: 'none' }}>#{pr.github_pr_number}</a>
                </td>
                <td style={{ padding: '10px', fontSize: '13px' }}>{pr.title}</td>
                <td style={{ padding: '10px', fontSize: '13px' }}>{pr.author}</td>
                <td style={{ padding: '10px' }}><code style={{ background: '#f4f4f4', padding: '2px 6px', borderRadius: '3px', fontSize: '11px' }}>{pr.source_branch}</code></td>
                <td style={{ padding: '10px', fontSize: '13px' }}>{pr.owner}/{pr.repo_name}</td>
                <td style={{ padding: '10px' }}>
                  <QAStatusBadge status={pr.qa_status} />
                </td>
              </tr>
            ))}
            {prs.length === 0 && <tr><td colSpan={7} style={{ padding: '20px', textAlign: 'center', color: '#999' }}>No PRs fetched yet. Click "Fetch PRs from GitHub".</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CommitTab({ tiers, onTriggered }: { tiers: string; onTriggered: () => void }) {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selectedRepo, setSelectedRepo] = useState('');
  const [commits, setCommits] = useState<Commit[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [fetching, setFetching] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [msg, setMsg] = useState('');
  const [commitStatuses, setCommitStatuses] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchApi<{ items: Repository[] }>('/api/github/repos')
      .then(d => { const a = d.items.filter(r => r.is_active); setRepos(a); if (a.length > 0) setSelectedRepo(a[0].id); })
      .catch(() => {});
    fetchApi<{ items: QAExecution[] }>('/api/qa/executions?limit=50&type=commit')
      .then(d => {
        const map: Record<string, string> = {};
        for (const e of d.items) {
          if (e.commit_sha && !map[e.commit_sha]) map[e.commit_sha] = e.status;
        }
        setCommitStatuses(map);
      }).catch(() => {});
  }, []);

  const fetchCommits = async () => {
    if (!selectedRepo) return;
    setFetching(true); setCommits([]); setSelected(new Set()); setMsg('');
    try {
      const d = await fetchApi<{ commits: Commit[] }>(`/api/github/repos/${selectedRepo}/commits?per_page=30`);
      setCommits(d.commits);
    } catch { setMsg('Failed to fetch commits.'); }
    setFetching(false);
  };

  const toggle = (sha: string) => setSelected(p => { const n = new Set(p); n.has(sha) ? n.delete(sha) : n.add(sha); return n; });

  const runQA = async () => {
    if (selected.size === 0) return;
    setExecuting(true); setMsg('');
    const repo = repos.find(r => r.id === selectedRepo);
    if (!repo) return;
    let ok = 0;
    for (const sha of selected) {
      try {
        await fetchApi('/api/qa/execute', { method: 'POST', body: JSON.stringify({
          repository_url: `https://github.com/${repo.owner}/${repo.repo_name}.git`,
          commit_sha: sha, tiers: tiers.split(',').map(Number), execution_type: 'commit',
        })});
        ok++;
        setCommitStatuses(prev => ({ ...prev, [sha]: 'pending' }));
      } catch { /* skip */ }
    }
    setMsg(`QA triggered for ${ok}/${selected.size} commits.`);
    setExecuting(false); setSelected(new Set());
    onTriggered();
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
        <select value={selectedRepo} onChange={e => { setSelectedRepo(e.target.value); setCommits([]); setSelected(new Set()); }}
          style={{ padding: '8px 12px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '13px', minWidth: '250px' }}>
          {repos.map(r => <option key={r.id} value={r.id}>{r.full_name}</option>)}
        </select>
        <button onClick={fetchCommits} disabled={!selectedRepo || fetching}
          style={{ padding: '8px 20px', background: selectedRepo && !fetching ? '#28a745' : '#ccc', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, fontSize: '13px', cursor: selectedRepo && !fetching ? 'pointer' : 'default' }}>
          {fetching ? 'Fetching...' : 'Fetch Commits'}
        </button>
        <button onClick={runQA} disabled={selected.size === 0 || executing}
          style={{ padding: '8px 24px', background: selected.size > 0 && !executing ? '#0f3460' : '#ccc', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, fontSize: '13px', cursor: selected.size > 0 && !executing ? 'pointer' : 'default' }}>
          {executing ? 'Running...' : `Run QA (${selected.size} selected)`}
        </button>
      </div>
      {msg && <StatusMsg msg={msg} />}
      {commits.length > 0 ? (
        <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
                <th style={{ padding: '10px', width: '40px' }}></th>
                <th style={{ padding: '10px', width: '90px' }}>SHA</th>
                <th style={{ padding: '10px' }}>Message</th>
                <th style={{ padding: '10px' }}>Author</th>
                <th style={{ padding: '10px' }}>Date</th>
                <th style={{ padding: '10px' }}>QA Status</th>
              </tr>
            </thead>
            <tbody>
              {commits.map(c => (
                <tr key={c.sha} onClick={() => toggle(c.sha)} style={{ borderBottom: '1px solid #f0f0f0', background: selected.has(c.sha) ? '#f0f7ff' : 'transparent', cursor: 'pointer' }}>
                  <td style={{ padding: '10px' }} onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={selected.has(c.sha)} onChange={() => toggle(c.sha)} />
                  </td>
                  <td style={{ padding: '10px' }}>
                    <a href={c.html_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}
                      style={{ fontFamily: 'monospace', fontSize: '12px', color: '#0f3460', fontWeight: 600, textDecoration: 'none' }}>{c.short_sha}</a>
                  </td>
                  <td style={{ padding: '10px', fontSize: '13px' }}>{c.message}</td>
                  <td style={{ padding: '10px', fontSize: '13px' }}>{c.author_login || c.author}</td>
                  <td style={{ padding: '10px', fontSize: '12px', color: '#666' }}>{new Date(c.date).toLocaleDateString()}</td>
                  <td style={{ padding: '10px' }}>
                    <QAStatusBadge status={commitStatuses[c.sha] || 'not_started'} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : !fetching && (
        <div style={{ background: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: '8px', padding: '20px', textAlign: 'center', color: '#999', fontSize: '14px' }}>
          Select a repository and click "Fetch Commits" to load recent commits.
        </div>
      )}
    </div>
  );
}

function ExecutionHistory({ executionType }: { executionType: string }) {
  const [executions, setExecutions] = useState<QAExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    let url = `/api/qa/executions?limit=20&type=${executionType}`;
    if (statusFilter) url += `&status=${statusFilter}`;
    fetchApi<{ items: QAExecution[] }>(url)
      .then(d => setExecutions(d.items)).catch(() => {}).finally(() => setLoading(false));
  }, [executionType, statusFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ marginTop: '30px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ margin: 0 }}>Execution History</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {STATUS_FILTERS.map(f => (
            <button key={f.key} style={filterPill(statusFilter === f.key)} onClick={() => setStatusFilter(f.key)}>{f.label}</button>
          ))}
          <button onClick={load} style={{ padding: '4px 14px', background: '#f0f0f0', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px', cursor: 'pointer', marginLeft: '8px' }}>Refresh</button>
        </div>
      </div>
      {loading ? <p style={{ color: '#999' }}>Loading...</p> : (
        <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
                <th style={{ padding: '10px' }}>ID</th>
                <th style={{ padding: '10px' }}>Repository</th>
                <th style={{ padding: '10px' }}>Branch / SHA</th>
                <th style={{ padding: '10px' }}>Status</th>
                <th style={{ padding: '10px' }}>Findings</th>
                <th style={{ padding: '10px' }}>Gate</th>
                <th style={{ padding: '10px' }}>Duration</th>
                <th style={{ padding: '10px' }}>Date</th>
              </tr>
            </thead>
            <tbody>
              {executions.map(e => (
                <tr key={e.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '10px', fontFamily: 'monospace', fontSize: '12px' }}>{e.scan_id || e.id.slice(0, 8)}</td>
                  <td style={{ padding: '10px' }}>{e.repository_url.replace(/\.git$/, '').split('/').slice(-2).join('/')}</td>
                  <td style={{ padding: '10px' }}><code style={{ background: '#f4f4f4', padding: '2px 6px', borderRadius: '3px', fontSize: '11px' }}>{e.commit_sha ? e.commit_sha.slice(0, 7) : e.branch || '—'}</code></td>
                  <td style={{ padding: '10px' }}><QAStatusBadge status={e.status} /></td>
                  <td style={{ padding: '10px' }}>{e.finding_count}</td>
                  <td style={{ padding: '10px' }}>
                    <span style={{ color: e.quality_gate_status === 'pass' ? '#28a745' : '#dc3545', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase' }}>{e.quality_gate_status || '—'}</span>
                  </td>
                  <td style={{ padding: '10px' }}>{(e.duration_seconds ?? 0) > 0 ? `${e.duration_seconds.toFixed(0)}s` : '—'}</td>
                  <td style={{ padding: '10px', fontSize: '12px', color: '#666' }}>{e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
              {executions.length === 0 && <tr><td colSpan={8} style={{ padding: '20px', textAlign: 'center', color: '#999' }}>No executions found.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatusMsg({ msg }: { msg: string }) {
  return <div style={{ background: '#e8f4fd', border: '1px solid #b8daff', borderRadius: '6px', padding: '10px 14px', marginBottom: '12px', fontSize: '13px' }}>{msg}</div>;
}
