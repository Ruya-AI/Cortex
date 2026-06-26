import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { fetchApi } from '../hooks/useApi';
import { PullRequest, QAExecution } from '../types';

interface Repository {
  id: string; owner: string; repo_name: string; full_name: string; description: string;
  default_branch: string; auto_fetch_prs: boolean; auto_qa_on_pr: boolean;
  qa_tiers: string; is_active: boolean;
}

interface RepoDetails {
  full_name: string; description: string; language: string; stars: number;
  forks: number; open_issues: number; default_branch: string; visibility: string;
  size_kb: number; license: string; topics: string[]; created_at: string;
  updated_at: string; pushed_at: string; owner_login: string; owner_type: string;
  owner_avatar: string; html_url: string;
  contributors: Array<{ login: string; avatar_url: string; contributions: number }>;
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
  const [expandedRepo, setExpandedRepo] = useState<string | null>(null);
  const [repoDetails, setRepoDetails] = useState<Record<string, RepoDetails>>({});

  useEffect(() => {
    fetchApi<{ items: Repository[] }>('/api/github/repos')
      .then(d => setRepos(d.items.filter(r => r.is_active))).catch(() => {});
  }, []);

  const toggle = (id: string) => setSelected(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const loadDetails = (id: string) => {
    if (expandedRepo === id) { setExpandedRepo(null); return; }
    setExpandedRepo(id);
    if (!repoDetails[id]) {
      fetchApi<RepoDetails>(`/api/github/repos/${id}/details`)
        .then(d => setRepoDetails(prev => ({ ...prev, [id]: d })))
        .catch(() => {});
    }
  };

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
      } catch { /* skip */ }
    }
    setMsg(`QA triggered for ${ok}/${sel.length} repositories.`);
    setExecuting(false); setSelected(new Set());
    onTriggered();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{ fontSize: '13px', color: '#666' }}>{repos.length} repositories configured</span>
        <button onClick={runQA} disabled={selected.size === 0 || executing}
          style={{ padding: '8px 24px', background: selected.size > 0 && !executing ? '#0f3460' : '#ccc', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, fontSize: '13px', cursor: selected.size > 0 && !executing ? 'pointer' : 'default' }}>
          {executing ? 'Running...' : `Run QA (${selected.size} selected)`}
        </button>
      </div>
      {msg && <StatusMsg msg={msg} />}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {repos.map(r => {
          const isSelected = selected.has(r.id);
          const isExpanded = expandedRepo === r.id;
          const details = repoDetails[r.id];
          return (
            <div key={r.id} style={{ background: '#fff', borderRadius: '8px', border: `1px solid ${isSelected ? '#0f3460' : '#dee2e6'}`, overflow: 'hidden' }}>
              {/* Row */}
              <div style={{ display: 'flex', alignItems: 'center', padding: '14px 16px', cursor: 'pointer', background: isSelected ? '#f0f7ff' : 'transparent' }}
                onClick={() => toggle(r.id)}>
                <input type="checkbox" checked={isSelected} onChange={() => toggle(r.id)} onClick={e => e.stopPropagation()} style={{ marginRight: '14px', cursor: 'pointer', width: '16px', height: '16px' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                    <a href={`https://github.com/${r.owner}/${r.repo_name}`} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}
                      style={{ fontWeight: 700, fontSize: '15px', color: '#0f3460', textDecoration: 'none' }}>{r.full_name}</a>
                    <code style={{ background: '#f4f4f4', padding: '2px 6px', borderRadius: '3px', fontSize: '11px', color: '#666' }}>{r.default_branch}</code>
                  </div>
                  <div style={{ fontSize: '13px', color: '#666' }}>{r.description || 'No description'}</div>
                </div>
                <button onClick={e => { e.stopPropagation(); loadDetails(r.id); }}
                  style={{ padding: '6px 14px', background: '#f0f0f0', border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px', cursor: 'pointer', color: '#333', marginLeft: '12px' }}>
                  {isExpanded ? 'Hide' : 'Details'}
                </button>
              </div>

              {/* Expanded Details */}
              {isExpanded && (
                <div style={{ borderTop: '1px solid #e9ecef', padding: '16px 20px', background: '#fafbfc' }}>
                  {details ? (
                    <div>
                      {/* Owner & Org */}
                      <div style={{ display: 'flex', gap: '24px', marginBottom: '16px', alignItems: 'center' }}>
                        {details.owner_avatar && <img src={details.owner_avatar} alt="" style={{ width: '40px', height: '40px', borderRadius: '50%', border: '1px solid #dee2e6' }} />}
                        <div>
                          <div style={{ fontSize: '14px', fontWeight: 600, color: '#333' }}>{details.owner_login}</div>
                          <div style={{ fontSize: '12px', color: '#666' }}>{details.owner_type}</div>
                        </div>
                        {details.visibility && <span style={{ background: details.visibility === 'private' ? '#ffc107' : '#28a745', color: details.visibility === 'private' ? '#333' : '#fff', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 600 }}>{details.visibility.toUpperCase()}</span>}
                      </div>

                      {/* Repo Info Grid */}
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '10px', marginBottom: '16px', fontSize: '13px' }}>
                        {details.language && <div><span style={{ color: '#999' }}>Language:</span> <strong>{details.language}</strong></div>}
                        <div><span style={{ color: '#999' }}>Stars:</span> <strong>{details.stars}</strong></div>
                        <div><span style={{ color: '#999' }}>Forks:</span> <strong>{details.forks}</strong></div>
                        <div><span style={{ color: '#999' }}>Open Issues:</span> <strong>{details.open_issues}</strong></div>
                        <div><span style={{ color: '#999' }}>Size:</span> <strong>{(details.size_kb / 1024).toFixed(1)} MB</strong></div>
                        {details.license && <div><span style={{ color: '#999' }}>License:</span> <strong>{details.license}</strong></div>}
                        <div><span style={{ color: '#999' }}>Created:</span> <strong>{new Date(details.created_at).toLocaleDateString()}</strong></div>
                        <div><span style={{ color: '#999' }}>Last Push:</span> <strong>{new Date(details.pushed_at).toLocaleDateString()}</strong></div>
                      </div>

                      {/* Topics */}
                      {details.topics.length > 0 && (
                        <div style={{ marginBottom: '16px' }}>
                          <span style={{ fontSize: '12px', color: '#999', marginRight: '8px' }}>Topics:</span>
                          {details.topics.map(t => (
                            <span key={t} style={{ display: 'inline-block', background: '#e8f0fe', color: '#0f3460', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', marginRight: '6px', marginBottom: '4px' }}>{t}</span>
                          ))}
                        </div>
                      )}

                      {/* Contributors */}
                      {details.contributors.length > 0 && (
                        <div>
                          <div style={{ fontSize: '13px', fontWeight: 600, color: '#333', marginBottom: '8px' }}>Major Contributors</div>
                          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                            {details.contributors.map(c => (
                              <div key={c.login} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                                <img src={c.avatar_url} alt="" style={{ width: '28px', height: '28px', borderRadius: '50%' }} />
                                <div>
                                  <div style={{ fontWeight: 500 }}>{c.login}</div>
                                  <div style={{ fontSize: '11px', color: '#999' }}>{c.contributions} commits</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', color: '#999', padding: '10px', fontSize: '13px' }}>Loading details...</div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {repos.length === 0 && (
          <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', padding: '30px', textAlign: 'center', color: '#999' }}>
            No repositories configured. Go to Admin to add.
          </div>
        )}
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
  const [loadError, setLoadError] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const load = useCallback(() => {
    setLoading(true); setLoadError('');
    let url = `/api/qa/executions?limit=20&type=${executionType}`;
    if (statusFilter) url += `&status=${statusFilter}`;
    fetchApi<{ items: QAExecution[] }>(url)
      .then(d => setExecutions(d.items))
      .catch((e: Error) => setLoadError(e.message || 'Failed to load executions'))
      .finally(() => setLoading(false));
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
          {executions.length > 0 && (
            <button onClick={() => {
              if (!confirm('Delete all finished executions?')) return;
              fetchApi(`/api/qa/executions${statusFilter ? `?status=${statusFilter}` : ''}`, { method: 'DELETE' })
                .then(() => load()).catch(() => {});
            }} style={{ padding: '4px 14px', background: '#dc3545', color: '#fff', border: 'none', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }}>Clean All</button>
          )}
        </div>
      </div>
      {loadError && <div style={{ background: '#fff3f3', border: '1px solid #f5c2c7', borderRadius: '6px', padding: '10px 14px', marginBottom: '12px', fontSize: '13px', color: '#dc3545' }}>{loadError} <button onClick={load} style={{ marginLeft: '8px', padding: '2px 10px', border: '1px solid #dc3545', borderRadius: '4px', background: '#fff', color: '#dc3545', cursor: 'pointer', fontSize: '12px' }}>Retry</button></div>}
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
                <th style={{ padding: '10px' }}></th>
              </tr>
            </thead>
            <tbody>
              {executions.map(e => (
                <tr key={e.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '10px', fontFamily: 'monospace', fontSize: '12px' }}>
                    <Link to={`/qa-execution/${e.id}`} style={{ color: '#0f3460', textDecoration: 'none', fontWeight: 600 }}>{e.scan_id || e.id.slice(0, 8)}</Link>
                  </td>
                  <td style={{ padding: '10px' }}>{e.repository_url.replace(/\.git$/, '').split('/').slice(-2).join('/')}</td>
                  <td style={{ padding: '10px' }}><code style={{ background: '#f4f4f4', padding: '2px 6px', borderRadius: '3px', fontSize: '11px' }}>{e.commit_sha ? e.commit_sha.slice(0, 7) : e.branch || '—'}</code></td>
                  <td style={{ padding: '10px' }}><QAStatusBadge status={e.status} /></td>
                  <td style={{ padding: '10px' }}>{e.finding_count}</td>
                  <td style={{ padding: '10px' }}>
                    <span style={{ color: e.quality_gate_status === 'pass' ? '#28a745' : '#dc3545', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase' }}>{e.quality_gate_status || '—'}</span>
                  </td>
                  <td style={{ padding: '10px' }}>{(e.duration_seconds ?? 0) > 0 ? `${e.duration_seconds.toFixed(0)}s` : '—'}</td>
                  <td style={{ padding: '10px', fontSize: '12px', color: '#666' }}>{e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}</td>
                  <td style={{ padding: '10px' }}>
                    {e.status !== 'running' && e.status !== 'pending' && (
                      <button onClick={() => { fetchApi(`/api/qa/executions/${e.id}`, { method: 'DELETE' }).then(() => load()).catch(() => {}); }}
                        style={{ padding: '3px 10px', background: '#dc3545', color: '#fff', border: 'none', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}>Delete</button>
                    )}
                  </td>
                </tr>
              ))}
              {executions.length === 0 && <tr><td colSpan={9} style={{ padding: '20px', textAlign: 'center', color: '#999' }}>No executions found.</td></tr>}
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
