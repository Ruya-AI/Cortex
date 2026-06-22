import { useEffect, useState } from 'react';
import { fetchApi } from '../hooks/useApi';
import { QAExecution as QAExecutionType } from '../types';

export function QAExecutionPage() {
  const [executions, setExecutions] = useState<QAExecutionType[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<{ items: QAExecutionType[] }>('/api/qa/executions?limit=50')
      .then(data => setExecutions(data.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2 style={{ marginBottom: '20px' }}>QA Execution History</h2>
      {loading ? <p style={{ color: '#999' }}>Loading...</p> : (
        <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
                <th style={{ padding: '10px' }}>ID</th>
                <th style={{ padding: '10px' }}>Repository</th>
                <th style={{ padding: '10px' }}>Branch</th>
                <th style={{ padding: '10px' }}>Tiers</th>
                <th style={{ padding: '10px' }}>Status</th>
                <th style={{ padding: '10px' }}>Findings</th>
                <th style={{ padding: '10px' }}>Severity</th>
                <th style={{ padding: '10px' }}>Gate</th>
                <th style={{ padding: '10px' }}>Duration</th>
              </tr>
            </thead>
            <tbody>
              {executions.map(e => (
                <tr key={e.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '10px', fontFamily: 'monospace', fontSize: '11px' }}>{e.scan_id || e.id.slice(0, 12)}</td>
                  <td style={{ padding: '10px' }}>{e.repository_url.split('/').pop()}</td>
                  <td style={{ padding: '10px', fontSize: '12px' }}>{e.branch || '—'}</td>
                  <td style={{ padding: '10px', fontSize: '12px' }}>{e.tiers}</td>
                  <td style={{ padding: '10px' }}>
                    <span style={{ color: e.status === 'completed' ? '#28a745' : e.status === 'failed' ? '#dc3545' : '#0d6efd', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase' }}>
                      {e.status}
                    </span>
                  </td>
                  <td style={{ padding: '10px', fontWeight: 600 }}>{e.finding_count}</td>
                  <td style={{ padding: '10px' }}>
                    {e.severity_counts && (
                      <span style={{ fontSize: '11px' }}>
                        {Object.entries(e.severity_counts).filter(([, v]) => v > 0).map(([k, v]) => `${k[0].toUpperCase()}:${v}`).join(' ')}
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '10px' }}>
                    <span style={{ color: e.quality_gate_status === 'pass' ? '#28a745' : '#dc3545', fontWeight: 600, fontSize: '12px' }}>
                      {e.quality_gate_status?.toUpperCase() || '—'}
                    </span>
                  </td>
                  <td style={{ padding: '10px', fontSize: '12px' }}>{e.duration_seconds > 0 ? `${Math.round(e.duration_seconds)}s` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
