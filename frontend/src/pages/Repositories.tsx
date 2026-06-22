import { useEffect, useState, useCallback } from 'react';
import { fetchApi } from '../hooks/useApi';

interface Repository {
  id: string;
  owner: string;
  repo_name: string;
  full_name: string;
  description: string;
  default_branch: string;
  auto_fetch_prs: boolean;
  auto_qa_on_pr: boolean;
  qa_tiers: string;
  is_active: boolean;
  created_at: string | null;
}

const TIER_OPTIONS = [
  { value: '1', label: 'Tier 1 only (deterministic tools)' },
  { value: '1,2', label: 'Tier 1 + 2 (tools + AI agents)' },
  { value: '1,2,3', label: 'All tiers (tools + agents + cross-file)' },
];

export function Repositories() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [executionStatus, setExecutionStatus] = useState<string>('');
  const [qaTiers, setQaTiers] = useState('1,2');

  const loadRepos = useCallback(() => {
    setLoading(true);
    fetchApi<{ items: Repository[] }>('/api/github/repos')
      .then(data => setRepos(data.items.filter(r => r.is_active)))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadRepos(); }, [loadRepos]);

  const onToggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const onSelectAll = useCallback(() => {
    if (selectedIds.size === repos.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(repos.map(r => r.id)));
    }
  }, [repos, selectedIds]);

  const onRunQA = async () => {
    if (selectedIds.size === 0) return;
    setExecuting(true);
    setExecutionStatus('');

    const selected = repos.filter(r => selectedIds.has(r.id));
    const tiers = qaTiers.split(',').map(Number);
    let completed = 0;
    const total = selected.length;

    for (const repo of selected) {
      setExecutionStatus(`Running QA on ${repo.full_name} (${completed + 1}/${total})...`);
      try {
        await fetchApi('/api/qa/execute', {
          method: 'POST',
          body: JSON.stringify({
            repository_url: `https://github.com/${repo.owner}/${repo.repo_name}.git`,
            branch: repo.default_branch,
            tiers,
          }),
        });
        completed++;
      } catch (e) {
        console.error(`QA failed for ${repo.full_name}:`, e);
      }
    }

    setExecutionStatus(`QA triggered for ${completed}/${total} repositories. Check QA Execution page for progress.`);
    setExecuting(false);
    setSelectedIds(new Set());
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ margin: 0 }}>Repositories</h2>
          <p style={{ color: '#666', fontSize: '13px', margin: '4px 0 0' }}>
            Select repositories and run QA. Single, multiple, or all.
          </p>
        </div>
      </div>

      {/* QA Controls */}
      <div style={{
        background: '#fff', border: '1px solid #dee2e6', borderRadius: '8px',
        padding: '16px 20px', marginBottom: '20px',
        display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label style={{ fontSize: '13px', fontWeight: 600, color: '#333' }}>QA Tiers:</label>
          <select
            value={qaTiers}
            onChange={e => setQaTiers(e.target.value)}
            style={{ padding: '6px 10px', border: '1px solid #ccc', borderRadius: '4px', fontSize: '13px' }}
          >
            {TIER_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <button
          onClick={onRunQA}
          disabled={selectedIds.size === 0 || executing}
          style={{
            padding: '8px 24px',
            background: selectedIds.size > 0 && !executing ? '#0f3460' : '#ccc',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: selectedIds.size > 0 && !executing ? 'pointer' : 'default',
            fontWeight: 600,
            fontSize: '14px',
          }}
        >
          {executing ? 'Running...' : `Run QA on ${selectedIds.size} selected`}
        </button>

        {selectedIds.size > 0 && (
          <span style={{ fontSize: '12px', color: '#666' }}>
            {selectedIds.size} of {repos.length} repositories selected
          </span>
        )}
      </div>

      {/* Execution status */}
      {executionStatus && (
        <div style={{
          background: executionStatus.includes('triggered') ? '#d4edda' : '#e8f4fd',
          border: `1px solid ${executionStatus.includes('triggered') ? '#c3e6cb' : '#b8daff'}`,
          borderRadius: '6px', padding: '12px 16px', marginBottom: '16px',
          fontSize: '13px', color: '#333',
        }}>
          {executionStatus}
        </div>
      )}

      {/* Repository Table */}
      {loading ? (
        <p style={{ color: '#999' }}>Loading repositories...</p>
      ) : repos.length === 0 ? (
        <div style={{
          background: '#fff', border: '1px solid #dee2e6', borderRadius: '8px',
          padding: '40px', textAlign: 'center', color: '#999',
        }}>
          <p style={{ fontSize: '16px', marginBottom: '8px' }}>No repositories configured</p>
          <p style={{ fontSize: '13px' }}>Go to Admin → Repository Management to add repositories.</p>
        </div>
      ) : (
        <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
                <th style={{ padding: '12px', width: '40px' }}>
                  <input
                    type="checkbox"
                    checked={selectedIds.size === repos.length && repos.length > 0}
                    onChange={onSelectAll}
                    title="Select All"
                    style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                  />
                </th>
                <th style={{ padding: '12px' }}>Repository</th>
                <th style={{ padding: '12px' }}>Description</th>
                <th style={{ padding: '12px' }}>Branch</th>
                <th style={{ padding: '12px' }}>QA Tiers</th>
                <th style={{ padding: '12px' }}>Auto-Fetch PRs</th>
                <th style={{ padding: '12px' }}>Auto QA on PR</th>
              </tr>
            </thead>
            <tbody>
              {repos.map(repo => {
                const isSelected = selectedIds.has(repo.id);
                return (
                  <tr
                    key={repo.id}
                    style={{
                      borderBottom: '1px solid #f0f0f0',
                      background: isSelected ? '#f0f7ff' : 'transparent',
                      cursor: 'pointer',
                    }}
                    onClick={() => onToggleSelect(repo.id)}
                  >
                    <td style={{ padding: '12px' }} onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => onToggleSelect(repo.id)}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                    </td>
                    <td style={{ padding: '12px' }}>
                      <a
                        href={`https://github.com/${repo.owner}/${repo.repo_name}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={e => e.stopPropagation()}
                        style={{ color: '#0f3460', fontWeight: 600, textDecoration: 'none' }}
                      >
                        {repo.full_name}
                      </a>
                    </td>
                    <td style={{ padding: '12px', color: '#666', fontSize: '13px' }}>
                      {repo.description || '—'}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <code style={{ background: '#f4f4f4', padding: '2px 6px', borderRadius: '3px', fontSize: '12px' }}>
                        {repo.default_branch}
                      </code>
                    </td>
                    <td style={{ padding: '12px', fontSize: '12px' }}>
                      {repo.qa_tiers.split(',').map(t => `Tier ${t.trim()}`).join(', ')}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        color: repo.auto_fetch_prs ? '#28a745' : '#adb5bd',
                        fontWeight: 600, fontSize: '12px',
                      }}>
                        {repo.auto_fetch_prs ? 'ON' : 'OFF'}
                      </span>
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        color: repo.auto_qa_on_pr ? '#28a745' : '#adb5bd',
                        fontWeight: 600, fontSize: '12px',
                      }}>
                        {repo.auto_qa_on_pr ? 'ON' : 'OFF'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
