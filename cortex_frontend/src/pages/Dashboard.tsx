import { useEffect, useState, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { MetricsCard } from '../components/MetricsCard';
import { ErrorBanner } from '../components/ErrorBanner';
import { fetchApi } from '../hooks/useApi';
import { QAExecution } from '../types';

interface ActiveExecution {
  executionId: string;
  repo: string;
  status: string;
  messages: string[];
  startedAt: number;
  findingCount?: number;
  qualityGate?: string;
  duration?: number;
}

interface AnalyticsDashboard {
  total_scans: number;
  total_findings: number;
  quality_gate_pass_rate: number;
  total_cost: number;
  avg_duration_seconds: number;
  total_prs_tracked: number;
  total_linear_tasks: number;
  severity_distribution: Record<string, number>;
}

interface PatternData {
  top_categories: Array<{ category: string; count: number }>;
  top_files: Array<{ file: string; count: number }>;
  top_sources: Array<{ source: string; count: number }>;
}

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/dashboard`;

const severityColors: Record<string, string> = {
  critical: '#dc3545', high: '#fd7e14', medium: '#ffc107', low: '#28a745', info: '#0d6efd',
};

const cardStyle: React.CSSProperties = {
  background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', padding: '20px',
};

export function Dashboard() {
  const [executions, setExecutions] = useState<QAExecution[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsDashboard | null>(null);
  const [patterns, setPatterns] = useState<PatternData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [active, setActive] = useState<Map<string, ActiveExecution>>(new Map());
  const [wsConnected, setWsConnected] = useState(false);
  const [now, setNow] = useState(Date.now());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = useCallback(() => {
    setError('');
    Promise.all([
      fetchApi<{ items: QAExecution[] }>('/api/qa/executions?limit=10').catch(() => ({ items: [] })),
      fetchApi<AnalyticsDashboard>('/api/analytics/dashboard').catch(() => null),
      fetchApi<PatternData>('/api/analytics/patterns').catch(() => null),
    ]).then(([execData, analyticsData, patternsData]) => {
      if (!analyticsData && execData.items.length === 0) setError('Failed to load dashboard data. Check that the backend is running.');
      setExecutions(execData.items);
      setAnalytics(analyticsData);
      setPatterns(patternsData);
      const running = execData.items.filter(e => e.status === 'running');
      if (running.length > 0) {
        setActive(prev => {
          const next = new Map(prev);
          for (const e of running) {
            if (!next.has(e.id)) {
              next.set(e.id, {
                executionId: e.id, repo: repoName(e.repository_url),
                status: 'running', messages: ['Scan in progress...'],
                startedAt: e.started_at ? new Date(e.started_at).getTime() : Date.now(),
              });
            }
          }
          return next;
        });
      }
    }).finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    let attempt = 0;
    function connect() {
      if (wsRef.current?.readyState === WebSocket.OPEN) return;
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => {
        setWsConnected(true); attempt = 0;
        pingRef.current = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send('ping'); }, 30000);
      };
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'status' || msg.type === 'progress') {
            const id = msg.execution_id;
            if (!id) return;
            setActive(prev => {
              const next = new Map(prev);
              const existing = next.get(id);
              if (msg.type === 'status' && msg.status === 'running') {
                next.set(id, { executionId: id, repo: repoName(msg.repository_url || ''), status: 'running', messages: [], startedAt: Date.now() });
              } else if (msg.type === 'progress') {
                const cur = existing || { executionId: id, repo: repoName(msg.repository_url || ''), status: 'running', messages: [], startedAt: Date.now() };
                next.set(id, { ...cur, messages: [...cur.messages, msg.message] });
              } else if (msg.type === 'status' && (msg.status === 'completed' || msg.status === 'failed')) {
                if (existing) next.set(id, { ...existing, status: msg.status, findingCount: msg.finding_count, qualityGate: msg.quality_gate_status, duration: msg.duration_seconds });
                setTimeout(() => { setActive(p => { const m = new Map(p); m.delete(id); return m; }); loadData(); }, 8000);
              }
              return next;
            });
          }
        } catch { /* ignore */ }
      };
      ws.onclose = () => {
        setWsConnected(false);
        if (pingRef.current) clearInterval(pingRef.current);
        reconnectRef.current = setTimeout(connect, Math.min(1000 * 2 ** attempt++, 15000));
      };
      ws.onerror = () => ws.close();
    }
    connect();
    return () => { wsRef.current?.close(); if (reconnectRef.current) clearTimeout(reconnectRef.current); if (pingRef.current) clearInterval(pingRef.current); };
  }, [loadData]);

  if (loading) return <div><h2>Dashboard</h2><p style={{ color: '#999' }}>Loading...</p></div>;
  if (error) return <div><h2>Dashboard</h2><ErrorBanner message={error} onRetry={loadData} /></div>;

  const stats = analytics || { total_scans: 0, total_findings: 0, quality_gate_pass_rate: 0, total_cost: 0, avg_duration_seconds: 0, total_prs_tracked: 0, total_linear_tasks: 0, severity_distribution: {} };
  const severityEntries = Object.entries(stats.severity_distribution || {});
  const totalSeverity = severityEntries.reduce((s, [, v]) => s + v, 0);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ margin: 0 }}>Dashboard</h2>
        <span style={{ fontSize: '11px', color: wsConnected ? '#28a745' : '#dc3545', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: wsConnected ? '#28a745' : '#dc3545', display: 'inline-block' }} />
          {wsConnected ? 'Live' : 'Disconnected'}
        </span>
      </div>

      {/* Metrics */}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '24px' }}>
        <MetricsCard title="Total Scans" value={stats.total_scans} />
        <MetricsCard title="Total Findings" value={stats.total_findings} />
        <MetricsCard title="Gate Pass Rate" value={`${(stats.quality_gate_pass_rate ?? 0).toFixed(0)}%`} color={stats.quality_gate_pass_rate >= 80 ? '#28a745' : '#dc3545'} />
        <MetricsCard title="Total Cost" value={`$${(stats.total_cost ?? 0).toFixed(2)}`} />
        <MetricsCard title="Avg Duration" value={`${(stats.avg_duration_seconds ?? 0).toFixed(0)}s`} />
        <MetricsCard title="PRs Tracked" value={stats.total_prs_tracked} />
        <MetricsCard title="Linear Tasks" value={stats.total_linear_tasks} />
      </div>

      {/* Live Progress */}
      {active.size > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            Live QA Progress
            <span style={{ background: '#0d6efd', color: '#fff', borderRadius: '10px', padding: '2px 8px', fontSize: '11px', fontWeight: 600 }}>{active.size} active</span>
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {Array.from(active.values()).map(exec => <ExecutionCard key={exec.executionId} exec={exec} now={now} />)}
          </div>
        </div>
      )}

      {/* Analytics Grid */}
      <div style={{ display: 'grid', gap: '20px', gridTemplateColumns: '1fr 1fr', marginBottom: '24px' }}>
        <div style={cardStyle}>
          <h4 style={{ marginTop: 0, marginBottom: '14px', color: '#0f3460' }}>Severity Distribution</h4>
          {severityEntries.length > 0 ? severityEntries.map(([sev, count]) => {
            const pct = totalSeverity > 0 ? (count / totalSeverity) * 100 : 0;
            return (
              <div key={sev} style={{ marginBottom: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '4px' }}>
                  <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>{sev}</span>
                  <span style={{ color: '#666' }}>{count} ({pct.toFixed(0)}%)</span>
                </div>
                <div style={{ background: '#f0f0f0', borderRadius: '4px', height: '8px', overflow: 'hidden' }}>
                  <div style={{ background: severityColors[sev] || '#6c757d', width: `${pct}%`, height: '100%', borderRadius: '4px' }} />
                </div>
              </div>
            );
          }) : <p style={{ color: '#999', fontSize: '13px' }}>No severity data yet.</p>}
        </div>

        <div style={cardStyle}>
          <h4 style={{ marginTop: 0, marginBottom: '14px', color: '#0f3460' }}>Top Categories</h4>
          {(patterns?.top_categories || []).length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <tbody>
                {patterns!.top_categories.slice(0, 8).map(c => (
                  <tr key={c.category} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '6px 0' }}>{c.category}</td>
                    <td style={{ padding: '6px 0', textAlign: 'right', fontWeight: 600 }}>{c.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p style={{ color: '#999', fontSize: '13px' }}>No category data yet.</p>}
        </div>

        <div style={cardStyle}>
          <h4 style={{ marginTop: 0, marginBottom: '14px', color: '#0f3460' }}>Top Files</h4>
          {(patterns?.top_files || []).length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <tbody>
                {patterns!.top_files.slice(0, 8).map(f => (
                  <tr key={f.file} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '6px 0', fontFamily: 'monospace', fontSize: '11px' }}>{f.file}</td>
                    <td style={{ padding: '6px 0', textAlign: 'right', fontWeight: 600 }}>{f.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p style={{ color: '#999', fontSize: '13px' }}>No file data yet.</p>}
        </div>

        <div style={cardStyle}>
          <h4 style={{ marginTop: 0, marginBottom: '14px', color: '#0f3460' }}>Top Sources</h4>
          {(patterns?.top_sources || []).length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <tbody>
                {patterns!.top_sources.slice(0, 8).map(s => (
                  <tr key={s.source} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '6px 0' }}>{s.source}</td>
                    <td style={{ padding: '6px 0', textAlign: 'right', fontWeight: 600 }}>{s.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p style={{ color: '#999', fontSize: '13px' }}>No source data yet.</p>}
        </div>
      </div>

      {/* Recent Executions */}
      <h3 style={{ marginBottom: '12px' }}>Recent QA Executions</h3>
      <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
              <th style={{ padding: '10px' }}>Scan ID</th>
              <th style={{ padding: '10px' }}>Repository</th>
              <th style={{ padding: '10px' }}>Type</th>
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
                <td style={{ padding: '10px', fontFamily: 'monospace', fontSize: '12px' }}>
                  <Link to={`/qa-execution/${e.id}`} style={{ color: '#0f3460', textDecoration: 'none', fontWeight: 600 }}>{e.scan_id || e.id.slice(0, 8)}</Link>
                </td>
                <td style={{ padding: '10px' }}>{repoName(e.repository_url)}</td>
                <td style={{ padding: '10px' }}>
                  <span style={{ fontSize: '11px', background: '#f0f0f0', padding: '2px 6px', borderRadius: '3px', textTransform: 'capitalize' }}>
                    {(e.execution_type || 'repository').replace('_', ' ')}
                  </span>
                </td>
                <td style={{ padding: '10px' }}>
                  <span style={{ color: e.status === 'completed' ? '#28a745' : e.status === 'failed' ? '#dc3545' : '#0d6efd', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase' }}>{e.status}</span>
                </td>
                <td style={{ padding: '10px' }}>{e.finding_count}</td>
                <td style={{ padding: '10px' }}>
                  <span style={{ color: e.quality_gate_status === 'pass' ? '#28a745' : '#dc3545', fontWeight: 600, fontSize: '12px', textTransform: 'uppercase' }}>{e.quality_gate_status || '—'}</span>
                </td>
                <td style={{ padding: '10px' }}>{(e.duration_seconds ?? 0) > 0 ? `${(e.duration_seconds ?? 0).toFixed(0)}s` : '—'}</td>
                <td style={{ padding: '10px', fontSize: '12px', color: '#666' }}>{e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}</td>
              </tr>
            ))}
            {executions.length === 0 && (
              <tr><td colSpan={8} style={{ padding: '20px', textAlign: 'center', color: '#999' }}>No executions yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function repoName(url: string): string {
  if (!url) return 'Unknown';
  return url.replace(/\.git$/, '').split('/').slice(-2).join('/');
}

function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}m ${s % 60}s` : `${s}s`;
}

function ExecutionCard({ exec, now }: { exec: ActiveExecution; now: number }) {
  const elapsed = now - exec.startedAt;
  const lastMessage = exec.messages[exec.messages.length - 1] || 'Starting...';
  const isDone = exec.status === 'completed' || exec.status === 'failed';
  const borderColor = isDone ? (exec.status === 'completed' ? '#28a745' : '#dc3545') : '#0d6efd';

  return (
    <div style={{ background: '#fff', border: `1px solid ${borderColor}`, borderLeft: `4px solid ${borderColor}`, borderRadius: '8px', padding: '16px 20px', opacity: isDone ? 0.85 : 1 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {!isDone && <Spinner />}
          <span style={{ fontWeight: 700, fontSize: '15px', color: '#0f3460' }}>{exec.repo}</span>
          <span style={{ background: isDone ? (exec.status === 'completed' ? '#d1e7dd' : '#f8d7da') : '#cfe2ff', color: isDone ? (exec.status === 'completed' ? '#198754' : '#dc3545') : '#0d6efd', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase' }}>{exec.status}</span>
        </div>
        <span style={{ fontSize: '13px', color: '#666', fontFamily: 'monospace' }}>{isDone && exec.duration ? `${exec.duration.toFixed(0)}s` : formatElapsed(elapsed)}</span>
      </div>
      <div style={{ fontSize: '13px', color: '#333' }}>{lastMessage}</div>
      {isDone && exec.status === 'completed' && (
        <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: '#666', marginTop: '6px' }}>
          <span>Findings: <strong>{exec.findingCount ?? 0}</strong></span>
          <span>Gate: <strong style={{ color: exec.qualityGate === 'pass' ? '#28a745' : '#dc3545' }}>{exec.qualityGate?.toUpperCase() || '—'}</strong></span>
        </div>
      )}
      {exec.messages.length > 1 && !isDone && (
        <details style={{ marginTop: '8px' }}>
          <summary style={{ fontSize: '11px', color: '#999', cursor: 'pointer' }}>{exec.messages.length} progress messages</summary>
          <div style={{ maxHeight: '120px', overflowY: 'auto', marginTop: '4px', fontSize: '11px', color: '#666', fontFamily: 'monospace', lineHeight: '1.6' }}>
            {exec.messages.map((m, i) => <div key={i}>{m}</div>)}
          </div>
        </details>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <span style={{ display: 'inline-block', width: '14px', height: '14px', border: '2px solid #dee2e6', borderTop: '2px solid #0d6efd', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </span>
  );
}
