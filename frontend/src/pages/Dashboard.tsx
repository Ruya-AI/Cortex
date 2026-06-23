import { useEffect, useState, useRef, useCallback } from 'react';
import { MetricsCard } from '../components/MetricsCard';
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

const WS_URL = `ws://${window.location.hostname}:8000/ws/dashboard`;

export function Dashboard() {
  const [executions, setExecutions] = useState<QAExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<Map<string, ActiveExecution>>(new Map());
  const [wsConnected, setWsConnected] = useState(false);
  const [now, setNow] = useState(Date.now());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadExecutions = useCallback(() => {
    fetchApi<{ items: QAExecution[] }>('/api/qa/executions?limit=10')
      .then(data => setExecutions(data.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadExecutions(); }, [loadExecutions]);

  // Seed active executions from any already-running scans on page load
  useEffect(() => {
    fetchApi<{ items: QAExecution[] }>('/api/qa/executions?limit=10')
      .then(data => {
        const running = data.items.filter(e => e.status === 'running');
        if (running.length > 0) {
          setActive(prev => {
            const next = new Map(prev);
            for (const e of running) {
              if (!next.has(e.id)) {
                next.set(e.id, {
                  executionId: e.id,
                  repo: repoName(e.repository_url),
                  status: 'running',
                  messages: ['Scan in progress...'],
                  startedAt: e.started_at ? new Date(e.started_at).getTime() : Date.now(),
                });
              }
            }
            return next;
          });
        }
      })
      .catch(() => {});
  }, []);

  // Elapsed time ticker
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  // WebSocket connection
  useEffect(() => {
    let attempt = 0;

    function connect() {
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        attempt = 0;
        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 30000);
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
                next.set(id, {
                  executionId: id,
                  repo: repoName(msg.repository_url || ''),
                  status: 'running',
                  messages: [],
                  startedAt: Date.now(),
                });
              } else if (msg.type === 'progress' && existing) {
                next.set(id, {
                  ...existing,
                  messages: [...existing.messages, msg.message],
                });
              } else if (msg.type === 'progress' && !existing) {
                next.set(id, {
                  executionId: id,
                  repo: repoName(msg.repository_url || ''),
                  status: 'running',
                  messages: [msg.message],
                  startedAt: Date.now(),
                });
              } else if (msg.type === 'status' && (msg.status === 'completed' || msg.status === 'failed')) {
                if (existing) {
                  next.set(id, {
                    ...existing,
                    status: msg.status,
                    findingCount: msg.finding_count,
                    qualityGate: msg.quality_gate_status,
                    duration: msg.duration_seconds,
                  });
                }
                setTimeout(() => {
                  setActive(p => { const m = new Map(p); m.delete(id); return m; });
                  loadExecutions();
                }, 8000);
              }

              return next;
            });
          }
        } catch { /* ignore non-JSON */ }
      };

      ws.onclose = () => {
        setWsConnected(false);
        if (pingRef.current) clearInterval(pingRef.current);
        const delay = Math.min(1000 * 2 ** attempt, 15000);
        attempt++;
        reconnectRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (pingRef.current) clearInterval(pingRef.current);
    };
  }, [loadExecutions]);

  const totalScans = executions.length;
  const totalFindings = executions.reduce((sum, e) => sum + e.finding_count, 0);
  const passRate = totalScans > 0
    ? Math.round((executions.filter(e => e.quality_gate_status === 'pass').length / totalScans) * 100)
    : 0;
  const totalCost = executions.reduce((sum, e) => sum + e.cost_usd, 0);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ margin: 0 }}>Executive Dashboard</h2>
        <span style={{
          fontSize: '11px',
          color: wsConnected ? '#28a745' : '#dc3545',
          display: 'flex', alignItems: 'center', gap: '5px',
        }}>
          <span style={{
            width: '8px', height: '8px', borderRadius: '50%',
            background: wsConnected ? '#28a745' : '#dc3545',
            display: 'inline-block',
          }} />
          {wsConnected ? 'Live' : 'Disconnected'}
        </span>
      </div>

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
                <td style={{ padding: '8px' }}>{repoName(e.repository_url)}</td>
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

      {/* Live QA Progress */}
      <div style={{ marginTop: '30px' }}>
        <h3 style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          Live QA Progress
          {active.size > 0 && (
            <span style={{
              background: '#0d6efd', color: '#fff', borderRadius: '10px',
              padding: '2px 8px', fontSize: '11px', fontWeight: 600,
            }}>
              {active.size} active
            </span>
          )}
        </h3>

        {active.size === 0 ? (
          <div style={{
            background: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: '8px',
            padding: '20px', textAlign: 'center', color: '#999', fontSize: '14px',
          }}>
            No active scans. Trigger QA from the Repositories page.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {Array.from(active.values()).map(exec => (
              <ExecutionCard key={exec.executionId} exec={exec} now={now} />
            ))}
          </div>
        )}
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
  const sec = s % 60;
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

function ExecutionCard({ exec, now }: { exec: ActiveExecution; now: number }) {
  const elapsed = now - exec.startedAt;
  const lastMessage = exec.messages[exec.messages.length - 1] || 'Starting...';
  const isDone = exec.status === 'completed' || exec.status === 'failed';

  const borderColor = isDone
    ? exec.status === 'completed' ? '#28a745' : '#dc3545'
    : '#0d6efd';

  return (
    <div style={{
      background: '#fff',
      border: `1px solid ${borderColor}`,
      borderLeft: `4px solid ${borderColor}`,
      borderRadius: '8px',
      padding: '16px 20px',
      transition: 'opacity 0.5s',
      opacity: isDone ? 0.85 : 1,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {!isDone && <Spinner />}
          <span style={{ fontWeight: 700, fontSize: '15px', color: '#0f3460' }}>{exec.repo}</span>
          <StatusBadge status={exec.status} />
        </div>
        <span style={{ fontSize: '13px', color: '#666', fontFamily: 'monospace' }}>
          {isDone && exec.duration ? `${exec.duration.toFixed(0)}s` : formatElapsed(elapsed)}
        </span>
      </div>

      <div style={{ fontSize: '13px', color: '#333', marginBottom: isDone ? '8px' : '0' }}>
        {lastMessage}
      </div>

      {isDone && exec.status === 'completed' && (
        <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: '#666', marginTop: '6px' }}>
          <span>Findings: <strong>{exec.findingCount ?? 0}</strong></span>
          <span>
            Gate:{' '}
            <strong style={{ color: exec.qualityGate === 'pass' ? '#28a745' : '#dc3545' }}>
              {exec.qualityGate?.toUpperCase() || '—'}
            </strong>
          </span>
        </div>
      )}

      {exec.messages.length > 1 && !isDone && (
        <details style={{ marginTop: '8px' }}>
          <summary style={{ fontSize: '11px', color: '#999', cursor: 'pointer' }}>
            {exec.messages.length} progress messages
          </summary>
          <div style={{
            maxHeight: '120px', overflowY: 'auto', marginTop: '4px',
            fontSize: '11px', color: '#666', fontFamily: 'monospace', lineHeight: '1.6',
          }}>
            {exec.messages.map((m, i) => <div key={i}>{m}</div>)}
          </div>
        </details>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    running: { bg: '#cfe2ff', fg: '#0d6efd' },
    completed: { bg: '#d1e7dd', fg: '#198754' },
    failed: { bg: '#f8d7da', fg: '#dc3545' },
  };
  const c = colors[status] || colors.running;
  return (
    <span style={{
      background: c.bg, color: c.fg,
      padding: '2px 8px', borderRadius: '10px',
      fontSize: '11px', fontWeight: 600, textTransform: 'uppercase',
    }}>
      {status}
    </span>
  );
}

function Spinner() {
  return (
    <span style={{
      display: 'inline-block', width: '14px', height: '14px',
      border: '2px solid #dee2e6', borderTop: '2px solid #0d6efd',
      borderRadius: '50%',
      animation: 'spin 0.8s linear infinite',
    }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </span>
  );
}
