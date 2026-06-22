import { useEffect, useState, useCallback } from 'react';
import { PRTable } from '../components/PRTable';
import { fetchApi } from '../hooks/useApi';
import { PullRequest } from '../types';

export function PullRequests() {
  const [pullRequests, setPullRequests] = useState<PullRequest[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);

  useEffect(() => {
    fetchApi<{ items: PullRequest[] }>('/api/pull-requests/')
      .then(data => setPullRequests(data.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const onToggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const onSelectAll = useCallback(() => {
    if (selectedIds.size === pullRequests.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pullRequests.map(pr => pr.id)));
    }
  }, [pullRequests, selectedIds]);

  const onRunQA = async () => {
    if (selectedIds.size === 0) return;
    setExecuting(true);
    // Trigger QA for each selected PR
    for (const id of selectedIds) {
      const pr = pullRequests.find(p => p.id === id);
      if (!pr) continue;
      try {
        await fetchApi('/api/qa/execute', {
          method: 'POST',
          body: JSON.stringify({
            repository_url: pr.html_url.replace(/\/pull\/\d+$/, ''),
            branch: pr.source_branch,
            pr_number: pr.github_pr_number,
            tiers: [1, 2],
          }),
        });
      } catch (e) {
        console.error('QA execution failed for PR', pr.github_pr_number, e);
      }
    }
    setExecuting(false);
    setSelectedIds(new Set());
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2>Pull Requests</h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={onRunQA}
            disabled={selectedIds.size === 0 || executing}
            style={{
              padding: '8px 20px',
              background: selectedIds.size > 0 ? '#0f3460' : '#ccc',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: selectedIds.size > 0 ? 'pointer' : 'default',
              fontWeight: 600,
            }}
          >
            {executing ? 'Running QA...' : `Run QA (${selectedIds.size} selected)`}
          </button>
        </div>
      </div>

      {loading ? (
        <p style={{ color: '#999' }}>Loading pull requests...</p>
      ) : (
        <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', overflow: 'hidden' }}>
          <PRTable pullRequests={pullRequests} selectedIds={selectedIds} onToggleSelect={onToggleSelect} onSelectAll={onSelectAll} />
        </div>
      )}
    </div>
  );
}
