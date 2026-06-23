import { useEffect, useState } from 'react';
import { MetricsCard } from '../components/MetricsCard';
import { fetchApi } from '../hooks/useApi';
import { QAExecution } from '../types';

interface AnalyticsDashboard {
  total_scans: number;
  total_findings: number;
  quality_gate_pass_rate: number;
  total_cost: number;
  avg_duration_seconds: number;
  total_prs_tracked: number;
  total_linear_tasks: number;
  severity_distribution: Record<string, number>;
  recent_executions: QAExecution[];
}

interface PatternData {
  top_categories: Array<{ category: string; count: number }>;
  top_files: Array<{ file: string; count: number }>;
  top_sources: Array<{ source: string; count: number }>;
}

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

const cardStyle: React.CSSProperties = {
  background: '#fff',
  borderRadius: '8px',
  border: '1px solid #dee2e6',
  padding: '20px',
};

const sectionHeading: React.CSSProperties = {
  marginBottom: '12px',
  color: '#0f3460',
};

const severityColors: Record<string, string> = {
  critical: '#dc3545',
  high: '#fd7e14',
  medium: '#ffc107',
  low: '#28a745',
  info: '#0d6efd',
};

export function Analytics() {
  const [dashboard, setDashboard] = useState<AnalyticsDashboard | null>(null);
  const [patterns, setPatterns] = useState<PatternData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchApi<AnalyticsDashboard>('/api/analytics/dashboard').catch(() => null),
      fetchApi<PatternData>('/api/analytics/patterns').catch(() => null),
    ])
      .then(([d, p]) => {
        setDashboard(d);
        setPatterns(p);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div>
        <h2 style={{ marginBottom: '20px' }}>Analytics</h2>
        <p style={{ color: '#999' }}>Loading analytics...</p>
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div>
        <h2 style={{ marginBottom: '20px' }}>Analytics</h2>
        <p style={{ color: '#666' }}>Analytics data is not yet available. Run some QA scans to generate insights.</p>
      </div>
    );
  }

  const severityEntries = Object.entries(dashboard.severity_distribution || {});
  const totalSeverity = severityEntries.reduce((s, [, v]) => s + v, 0);

  return (
    <div>
      <h2 style={{ marginBottom: '20px' }}>Analytics</h2>

      {/* Executive Metrics */}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '30px' }}>
        <MetricsCard title="Total Scans" value={dashboard.total_scans} />
        <MetricsCard title="Total Findings" value={dashboard.total_findings} />
        <MetricsCard
          title="Gate Pass Rate"
          value={`${dashboard.quality_gate_pass_rate.toFixed(0)}%`}
          color={dashboard.quality_gate_pass_rate >= 80 ? '#28a745' : '#dc3545'}
        />
        <MetricsCard title="Total Cost" value={`$${(dashboard.total_cost ?? 0).toFixed(2)}`} />
        <MetricsCard title="Avg Duration" value={`${(dashboard.avg_duration_seconds ?? 0).toFixed(0)}s`} />
        <MetricsCard title="PRs Tracked" value={dashboard.total_prs_tracked} />
        <MetricsCard title="Linear Tasks" value={dashboard.total_linear_tasks} />
      </div>

      <div style={{ display: 'grid', gap: '20px', gridTemplateColumns: '1fr 1fr', marginBottom: '30px' }}>
        {/* Severity Distribution */}
        <div style={cardStyle}>
          <h3 style={sectionHeading}>Severity Distribution</h3>
          {severityEntries.length > 0 ? (
            severityEntries.map(([severity, count]) => {
              const pct = totalSeverity > 0 ? (count / totalSeverity) * 100 : 0;
              return (
                <div key={severity} style={{ marginBottom: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '4px' }}>
                    <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>{severity}</span>
                    <span style={{ color: '#666' }}>{count} ({pct.toFixed(0)}%)</span>
                  </div>
                  <div style={{ background: '#f0f0f0', borderRadius: '4px', height: '8px', overflow: 'hidden' }}>
                    <div style={{ background: severityColors[severity] || '#6c757d', width: `${pct}%`, height: '100%', borderRadius: '4px' }} />
                  </div>
                </div>
              );
            })
          ) : (
            <p style={{ color: '#999', fontSize: '14px' }}>No severity data available.</p>
          )}
        </div>

        {/* Top Finding Categories */}
        <div style={cardStyle}>
          <h3 style={sectionHeading}>Top Finding Categories</h3>
          {(patterns?.top_categories || []).length > 0 ? (
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>Category</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>Count</th>
                </tr>
              </thead>
              <tbody>
                {patterns!.top_categories.map(cat => (
                  <tr key={cat.category}>
                    <td style={tdStyle}>{cat.category}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600 }}>{cat.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ color: '#999', fontSize: '14px' }}>No category data available.</p>
          )}
        </div>

        {/* Top Files */}
        <div style={cardStyle}>
          <h3 style={sectionHeading}>Top Files with Most Findings</h3>
          {(patterns?.top_files || []).length > 0 ? (
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>File</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>Findings</th>
                </tr>
              </thead>
              <tbody>
                {patterns!.top_files.map(f => (
                  <tr key={f.file}>
                    <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: '12px' }}>{f.file}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600 }}>{f.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ color: '#999', fontSize: '14px' }}>No file data available.</p>
          )}
        </div>

        {/* Top Sources */}
        <div style={cardStyle}>
          <h3 style={sectionHeading}>Top Sources (Tools / Agents)</h3>
          {(patterns?.top_sources || []).length > 0 ? (
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>Source</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>Findings</th>
                </tr>
              </thead>
              <tbody>
                {patterns!.top_sources.map(s => (
                  <tr key={s.source}>
                    <td style={tdStyle}>{s.source}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600 }}>{s.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ color: '#999', fontSize: '14px' }}>No source data available.</p>
          )}
        </div>
      </div>

      {/* Recent Executions */}
      <div style={cardStyle}>
        <h3 style={sectionHeading}>Recent Executions</h3>
        {(dashboard.recent_executions || []).length > 0 ? (
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Scan ID</th>
                <th style={thStyle}>Repository</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Findings</th>
                <th style={thStyle}>Gate</th>
                <th style={thStyle}>Duration</th>
                <th style={thStyle}>Cost</th>
                <th style={thStyle}>Date</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.recent_executions.map(e => (
                <tr key={e.id}>
                  <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: '12px' }}>{e.scan_id || e.id.slice(0, 8)}</td>
                  <td style={tdStyle}>{e.repository_url.split('/').pop()}</td>
                  <td style={tdStyle}>
                    <span style={{ color: e.status === 'completed' ? '#28a745' : e.status === 'failed' ? '#dc3545' : '#0d6efd', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase' }}>
                      {e.status}
                    </span>
                  </td>
                  <td style={tdStyle}>{e.finding_count}</td>
                  <td style={tdStyle}>
                    <span style={{ color: e.quality_gate_status === 'pass' ? '#28a745' : '#dc3545', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase' }}>
                      {e.quality_gate_status || '—'}
                    </span>
                  </td>
                  <td style={tdStyle}>{(e.duration_seconds ?? 0) > 0 ? `${e.duration_seconds.toFixed(0)}s` : '—'}</td>
                  <td style={tdStyle}>${(e.cost_usd ?? 0).toFixed(4)}</td>
                  <td style={{ ...tdStyle, fontSize: '12px', color: '#666' }}>{e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ color: '#999', fontSize: '14px' }}>No recent executions found.</p>
        )}
      </div>
    </div>
  );
}
