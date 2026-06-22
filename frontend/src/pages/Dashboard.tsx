import { useEffect, useState } from 'react';
import { MetricsCard } from '../components/MetricsCard';
import { fetchApi } from '../hooks/useApi';
import { QAExecution } from '../types';

export function Dashboard() {
  const [executions, setExecutions] = useState<QAExecution[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<{ items: QAExecution[] }>('/api/qa/executions?limit=10')
      .then(data => setExecutions(data.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const totalScans = executions.length;
  const totalFindings = executions.reduce((sum, e) => sum + e.finding_count, 0);
  const passRate = totalScans > 0
    ? Math.round((executions.filter(e => e.quality_gate_status === 'pass').length / totalScans) * 100)
    : 0;
  const totalCost = executions.reduce((sum, e) => sum + e.cost_usd, 0);

  return (
    <div>
      <h2 style={{ marginBottom: '20px' }}>Executive Dashboard</h2>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '30px' }}>
        <MetricsCard title="Total Scans" value={totalScans} />
        <MetricsCard title="Total Findings" value={totalFindings} />
        <MetricsCard title="Gate Pass Rate" value={`${passRate}%`} color={passRate >= 80 ? '#28a745' : '#dc3545'} />
        <MetricsCard title="Total Cost" value={`$${totalCost.toFixed(2)}`} />
      </div>

      <h3 style={{ marginBottom: '12px' }}>Recent QA Executions</h3>
      {loading ? (
        <p style={{ color: '#999' }}>Loading...</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
              <th style={{ padding: '8px' }}>Scan ID</th>
              <th style={{ padding: '8px' }}>Repository</th>
              <th style={{ padding: '8px' }}>Status</th>
              <th style={{ padding: '8px' }}>Findings</th>
              <th style={{ padding: '8px' }}>Gate</th>
              <th style={{ padding: '8px' }}>Duration</th>
              <th style={{ padding: '8px' }}>Cost</th>
              <th style={{ padding: '8px' }}>Date</th>
            </tr>
          </thead>
          <tbody>
            {executions.map(e => (
              <tr key={e.id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                <td style={{ padding: '8px', fontFamily: 'monospace', fontSize: '12px' }}>{e.scan_id || e.id.slice(0, 8)}</td>
                <td style={{ padding: '8px' }}>{e.repository_url.split('/').pop()}</td>
                <td style={{ padding: '8px' }}>
                  <span style={{ color: e.status === 'completed' ? '#28a745' : e.status === 'failed' ? '#dc3545' : '#0d6efd', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase' }}>
                    {e.status}
                  </span>
                </td>
                <td style={{ padding: '8px' }}>{e.finding_count}</td>
                <td style={{ padding: '8px' }}>
                  <span style={{ color: e.quality_gate_status === 'pass' ? '#28a745' : '#dc3545', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase' }}>
                    {e.quality_gate_status || '—'}
                  </span>
                </td>
                <td style={{ padding: '8px' }}>{e.duration_seconds > 0 ? `${e.duration_seconds.toFixed(0)}s` : '—'}</td>
                <td style={{ padding: '8px' }}>${e.cost_usd.toFixed(4)}</td>
                <td style={{ padding: '8px', fontSize: '12px', color: '#666' }}>{e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
