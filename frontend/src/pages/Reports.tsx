import { useEffect, useState } from 'react';
import { fetchApi } from '../hooks/useApi';
import { QAExecution } from '../types';

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '14px',
};

const thStyle: React.CSSProperties = {
  padding: '8px',
  textAlign: 'left',
  borderBottom: '2px solid #dee2e6',
};

const tdStyle: React.CSSProperties = {
  padding: '8px',
  borderBottom: '1px solid #f0f0f0',
};

const downloadBtnStyle: React.CSSProperties = {
  padding: '4px 10px',
  border: '1px solid #0f3460',
  borderRadius: '4px',
  background: 'transparent',
  color: '#0f3460',
  cursor: 'pointer',
  fontWeight: 500,
  fontSize: '11px',
  marginRight: '4px',
};

const cardStyle: React.CSSProperties = {
  background: '#fff',
  borderRadius: '8px',
  border: '1px solid #dee2e6',
  padding: '20px',
};

const FILTERS = [
  { key: '', label: 'All' },
  { key: 'repository', label: 'Repository' },
  { key: 'pull_request', label: 'Pull Request' },
  { key: 'commit', label: 'Commit' },
];

const filterPillStyle = (active: boolean): React.CSSProperties => ({
  padding: '6px 16px', borderRadius: '20px', fontSize: '13px', fontWeight: active ? 600 : 400,
  border: active ? '2px solid #0f3460' : '1px solid #ccc',
  background: active ? '#e8f0fe' : '#fff', color: active ? '#0f3460' : '#666',
  cursor: 'pointer',
});

export function Reports() {
  const [executions, setExecutions] = useState<QAExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<QAExecution | null>(null);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    setLoading(true);
    const url = filter ? `/api/qa/executions?limit=50&type=${filter}` : '/api/qa/executions?limit=50';
    fetchApi<{ items: QAExecution[] }>(url)
      .then(data => setExecutions(data.items || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filter]);

  const download = (executionId: string, type: string) => {
    window.open(`/api/reports/${executionId}/download/${type}`, '_blank');
  };

  return (
    <div>
      <h2 style={{ marginBottom: '16px' }}>Reports</h2>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        {FILTERS.map(f => (
          <button key={f.key} style={filterPillStyle(filter === f.key)} onClick={() => { setFilter(f.key); setSelected(null); }}>
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p style={{ color: '#999' }}>Loading executions...</p>
      ) : executions.length === 0 ? (
        <p style={{ color: '#666' }}>No QA executions found. Run a scan to generate reports.</p>
      ) : (
        <>
          <div style={{ ...cardStyle, marginBottom: '20px' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>Scan ID</th>
                  <th style={thStyle}>Repository</th>
                  <th style={thStyle}>Type</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Findings</th>
                  <th style={thStyle}>Gate</th>
                  <th style={thStyle}>Date</th>
                  <th style={thStyle}>Downloads</th>
                </tr>
              </thead>
              <tbody>
                {executions.map(e => (
                  <tr
                    key={e.id}
                    onClick={() => setSelected(e)}
                    style={{
                      cursor: 'pointer',
                      background: selected?.id === e.id ? '#f0f4ff' : 'transparent',
                    }}
                  >
                    <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: '12px' }}>
                      {e.scan_id || e.id.slice(0, 8)}
                    </td>
                    <td style={tdStyle}>{e.repository_url.split('/').pop()}</td>
                    <td style={tdStyle}>
                      <span style={{ fontSize: '11px', background: '#f0f0f0', padding: '2px 6px', borderRadius: '3px', textTransform: 'capitalize' }}>
                        {(e.execution_type || 'repository').replace('_', ' ')}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{
                        color: e.status === 'completed' ? '#28a745' : e.status === 'failed' ? '#dc3545' : '#0d6efd',
                        fontWeight: 600,
                        fontSize: '12px',
                        textTransform: 'uppercase',
                      }}>
                        {e.status}
                      </span>
                    </td>
                    <td style={tdStyle}>{e.finding_count}</td>
                    <td style={tdStyle}>
                      <span style={{
                        color: e.quality_gate_status === 'pass' ? '#28a745' : '#dc3545',
                        fontWeight: 600,
                        fontSize: '12px',
                        textTransform: 'uppercase',
                      }}>
                        {e.quality_gate_status || '—'}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, fontSize: '12px', color: '#666' }}>
                      {e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td style={tdStyle} onClick={ev => ev.stopPropagation()}>
                      <button style={downloadBtnStyle} onClick={() => download(e.id, 'full-json')}>JSON</button>
                      <button style={downloadBtnStyle} onClick={() => download(e.id, 'full-pdf')}>PDF</button>
                      <button style={downloadBtnStyle} onClick={() => download(e.id, 'executive-json')}>Exec JSON</button>
                      <button style={downloadBtnStyle} onClick={() => download(e.id, 'executive-pdf')}>Exec PDF</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Findings Summary */}
          {selected && (
            <div style={cardStyle}>
              <h3 style={{ marginBottom: '12px', color: '#0f3460' }}>
                Findings Summary — {selected.scan_id || selected.id.slice(0, 8)}
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '12px', marginBottom: '16px' }}>
                <div style={{ padding: '12px', background: '#f8f9fa', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 700 }}>{selected.finding_count}</div>
                  <div style={{ fontSize: '11px', color: '#6c757d', textTransform: 'uppercase' }}>Total Findings</div>
                </div>
                <div style={{ padding: '12px', background: '#f8f9fa', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: selected.quality_gate_status === 'pass' ? '#28a745' : '#dc3545' }}>
                    {(selected.quality_gate_status || '—').toUpperCase()}
                  </div>
                  <div style={{ fontSize: '11px', color: '#6c757d', textTransform: 'uppercase' }}>Gate Status</div>
                </div>
                <div style={{ padding: '12px', background: '#f8f9fa', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 700 }}>
                    {(selected.duration_seconds ?? 0) > 0 ? `${selected.duration_seconds.toFixed(0)}s` : '—'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#6c757d', textTransform: 'uppercase' }}>Duration</div>
                </div>
                <div style={{ padding: '12px', background: '#f8f9fa', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 700 }}>${(selected.cost_usd ?? 0).toFixed(4)}</div>
                  <div style={{ fontSize: '11px', color: '#6c757d', textTransform: 'uppercase' }}>Cost</div>
                </div>
              </div>
              {selected.severity_counts && Object.keys(selected.severity_counts).length > 0 && (
                <div>
                  <h4 style={{ fontSize: '14px', color: '#333', marginBottom: '8px' }}>By Severity</h4>
                  <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                    {Object.entries(selected.severity_counts).map(([severity, count]) => (
                      <div key={severity} style={{ fontSize: '13px' }}>
                        <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>{severity}: </span>
                        <span style={{ fontWeight: 700 }}>{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {selected.error_message && (
                <div style={{ marginTop: '12px', padding: '10px', background: '#fff3f3', border: '1px solid #ffcccc', borderRadius: '4px', fontSize: '13px', color: '#dc3545' }}>
                  {selected.error_message}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
