import { PullRequest } from '../types';

interface PRTableProps {
  pullRequests: PullRequest[];
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onSelectAll: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#6c757d',
  running: '#0d6efd',
  completed: '#28a745',
  failed: '#dc3545',
  skipped: '#adb5bd',
};

export function PRTable({ pullRequests, selectedIds, onToggleSelect, onSelectAll }: PRTableProps) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
      <thead>
        <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
          <th style={{ padding: '10px' }}>
            <input type="checkbox" onChange={onSelectAll} checked={selectedIds.size === pullRequests.length && pullRequests.length > 0} />
          </th>
          <th style={{ padding: '10px' }}>PR</th>
          <th style={{ padding: '10px' }}>Title</th>
          <th style={{ padding: '10px' }}>Author</th>
          <th style={{ padding: '10px' }}>Branch</th>
          <th style={{ padding: '10px' }}>Changes</th>
          <th style={{ padding: '10px' }}>QA Status</th>
        </tr>
      </thead>
      <tbody>
        {pullRequests.map(pr => (
          <tr key={pr.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
            <td style={{ padding: '10px' }}>
              <input type="checkbox" checked={selectedIds.has(pr.id)} onChange={() => onToggleSelect(pr.id)} />
            </td>
            <td style={{ padding: '10px' }}>
              <a href={pr.html_url} target="_blank" rel="noopener noreferrer" style={{ color: '#0f3460', fontWeight: 600 }}>
                #{pr.github_pr_number}
              </a>
            </td>
            <td style={{ padding: '10px' }}>{pr.title}</td>
            <td style={{ padding: '10px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {pr.author_avatar_url && <img src={pr.author_avatar_url} alt="" style={{ width: 20, height: 20, borderRadius: '50%' }} />}
                {pr.author}
              </span>
            </td>
            <td style={{ padding: '10px', fontSize: '12px', color: '#666' }}>
              {pr.source_branch} → {pr.target_branch}
            </td>
            <td style={{ padding: '10px', fontSize: '12px' }}>
              <span style={{ color: '#28a745' }}>+{pr.additions}</span>{' '}
              <span style={{ color: '#dc3545' }}>-{pr.deletions}</span>{' '}
              ({pr.changed_files} files)
            </td>
            <td style={{ padding: '10px' }}>
              <span style={{
                color: STATUS_COLORS[pr.qa_status] || '#666',
                fontWeight: 600,
                fontSize: '12px',
                textTransform: 'uppercase',
              }}>
                {pr.qa_status}
              </span>
            </td>
          </tr>
        ))}
        {pullRequests.length === 0 && (
          <tr>
            <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#999' }}>
              No pull requests found. Configure a repository and fetch PRs to get started.
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}
