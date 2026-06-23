import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchApi } from '../hooks/useApi';
import { QAExecution, QAFinding } from '../types';

type TabKey = 'full' | 'executive';

const severityColors: Record<string, string> = {
  critical: '#dc3545', high: '#fd7e14', medium: '#ffc107', low: '#28a745', info: '#0d6efd',
};

const statusColors: Record<string, { bg: string; fg: string }> = {
  completed: { bg: '#d1e7dd', fg: '#198754' },
  failed: { bg: '#f8d7da', fg: '#dc3545' },
  running: { bg: '#cfe2ff', fg: '#0d6efd' },
  pending: { bg: '#cfe2ff', fg: '#0d6efd' },
  cancelled: { bg: '#e9ecef', fg: '#6c757d' },
};

const cardStyle: React.CSSProperties = {
  background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', padding: '20px', marginBottom: '20px',
};

export function ExecutionDetail() {
  const { id } = useParams<{ id: string }>();
  const [exec, setExec] = useState<QAExecution | null>(null);
  const [findings, setFindings] = useState<QAFinding[]>([]);
  const [findingsTotal, setFindingsTotal] = useState(0);
  const [tab, setTab] = useState<TabKey>('full');
  const [loading, setLoading] = useState(true);
  const [sevFilter, setSevFilter] = useState('');
  const [expandedFinding, setExpandedFinding] = useState<string | null>(null);
  const [expandedDetail, setExpandedDetail] = useState<QAFinding | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchApi<QAExecution>(`/api/qa/executions/${id}`)
      .then(setExec)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const url = sevFilter
      ? `/api/reports/${id}/findings?limit=200&severity=${sevFilter}`
      : `/api/reports/${id}/findings?limit=200`;
    fetchApi<{ items: QAFinding[]; total: number }>(url)
      .then(d => { setFindings(d.items); setFindingsTotal(d.total); })
      .catch(() => {});
  }, [id, sevFilter]);

  const loadFullFinding = (findingId: string) => {
    if (expandedFinding === findingId) { setExpandedFinding(null); setExpandedDetail(null); return; }
    setExpandedFinding(findingId);
    fetchApi<QAFinding>(`/api/reports/${id}/findings/${findingId}`)
      .then(setExpandedDetail)
      .catch(() => setExpandedDetail(null));
  };

  if (loading) return <div><p style={{ color: '#999' }}>Loading execution...</p></div>;
  if (!exec) return <div><p style={{ color: '#dc3545' }}>Execution not found.</p><Link to="/qa-execution" style={{ color: '#0f3460' }}>Back to QA Execution</Link></div>;

  const repoName = exec.repository_url.replace(/\.git$/, '').split('/').slice(-2).join('/');
  const isFailed = exec.status === 'failed';
  const isIncomplete = exec.status === 'cancelled' || (exec.status === 'running' && exec.completed_at !== null);
  const sc = statusColors[exec.status] || statusColors.pending;
  const logLines = (exec.execution_log || '').split('\n').filter(Boolean);
  const lastStep = logLines.length > 0 ? logLines[logLines.length - 1] : null;
  const sevEntries = Object.entries(exec.severity_counts || {});
  const totalSev = sevEntries.reduce((s, [, v]) => s + v, 0);

  const download = (type: string) => window.open(`/api/reports/${exec.id}/download/${type}`, '_blank');
  const hasReports = !!(exec.report_json_path || exec.executive_json_path);

  const tabBtn = (key: TabKey, label: string) => (
    <button onClick={() => setTab(key)} style={{
      padding: '8px 24px', fontSize: '14px', fontWeight: tab === key ? 700 : 400,
      borderBottom: tab === key ? '3px solid #0f3460' : '3px solid transparent',
      color: tab === key ? '#0f3460' : '#666', background: 'none', border: 'none', cursor: 'pointer',
    }}>{label}</button>
  );

  return (
    <div>
      {/* Breadcrumb */}
      <div style={{ fontSize: '13px', color: '#666', marginBottom: '16px' }}>
        <Link to="/qa-execution" style={{ color: '#0f3460', textDecoration: 'none' }}>QA Execution</Link>
        <span style={{ margin: '0 8px' }}>/</span>
        <span>{exec.scan_id || exec.id.slice(0, 8)}</span>
      </div>

      {/* Header */}
      <div style={{ ...cardStyle, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2 style={{ margin: '0 0 8px', color: '#0f3460' }}>{repoName}</h2>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap', fontSize: '13px', color: '#666' }}>
            <span style={{ background: sc.bg, color: sc.fg, padding: '3px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase' }}>{exec.status}</span>
            <span style={{ background: '#f0f0f0', padding: '2px 8px', borderRadius: '4px', textTransform: 'capitalize' }}>{(exec.execution_type || 'repository').replace('_', ' ')}</span>
            {exec.branch && <span>Branch: <code style={{ background: '#f4f4f4', padding: '2px 6px', borderRadius: '3px' }}>{exec.commit_sha ? exec.commit_sha.slice(0, 7) : exec.branch}</code></span>}
            {exec.tiers && <span>Tiers: {exec.tiers}</span>}
          </div>
        </div>
        <div style={{ textAlign: 'right', fontSize: '13px', color: '#666' }}>
          {exec.started_at && <div>Started: {new Date(exec.started_at).toLocaleString()}</div>}
          {exec.completed_at && <div>Completed: {new Date(exec.completed_at).toLocaleString()}</div>}
          {(exec.duration_seconds ?? 0) > 0 && <div>Duration: <strong>{(exec.duration_seconds ?? 0).toFixed(0)}s</strong></div>}
          {(exec.cost_usd ?? 0) > 0 && <div>Cost: <strong>${(exec.cost_usd ?? 0).toFixed(4)}</strong></div>}
        </div>
      </div>

      {/* Failed/Incomplete Banner */}
      {(isFailed || isIncomplete) && (
        <div style={{ background: '#fff3f3', border: '1px solid #f5c2c7', borderLeft: '4px solid #dc3545', borderRadius: '8px', padding: '16px 20px', marginBottom: '20px' }}>
          <div style={{ fontWeight: 700, color: '#dc3545', marginBottom: '6px' }}>
            {isFailed ? 'Execution Failed' : 'Execution Incomplete'}
          </div>
          {exec.error_message && <div style={{ fontSize: '13px', color: '#842029', marginBottom: '8px', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>{exec.error_message}</div>}
          {lastStep && (
            <div style={{ fontSize: '12px', color: '#666' }}>
              Last completed step: <strong>{lastStep}</strong>
            </div>
          )}
          {logLines.length === 0 && !exec.error_message && (
            <div style={{ fontSize: '13px', color: '#999' }}>No execution details available.</div>
          )}
        </div>
      )}

      {/* Tab Bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid #dee2e6', marginBottom: '20px', gap: '4px' }}>
        {tabBtn('full', 'Full Audit Report')}
        {tabBtn('executive', 'Executive Summary')}
      </div>

      {/* Full Audit Report Tab */}
      {tab === 'full' && (
        <div>
          {/* Download Buttons */}
          {hasReports && (
            <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
              {exec.report_json_path && <DownloadBtn label="Full Report (JSON)" onClick={() => download('full-json')} />}
              {exec.report_pdf_path && <DownloadBtn label="Full Report (PDF)" onClick={() => download('full-pdf')} />}
              {exec.executive_json_path && <DownloadBtn label="Executive (JSON)" onClick={() => download('executive-json')} />}
              {exec.executive_pdf_path && <DownloadBtn label="Executive (PDF)" onClick={() => download('executive-pdf')} />}
            </div>
          )}
          {!hasReports && (
            <div style={{ ...cardStyle, textAlign: 'center', color: '#999' }}>
              {isFailed ? 'Reports not available — execution failed before report generation.' : 'No reports generated for this execution.'}
            </div>
          )}

          {/* Execution Log */}
          {logLines.length > 0 && (
            <details style={{ marginBottom: '20px' }}>
              <summary style={{ cursor: 'pointer', fontSize: '14px', fontWeight: 600, color: '#0f3460', padding: '10px 0' }}>
                Execution Log ({logLines.length} entries)
              </summary>
              <div style={{ ...cardStyle, maxHeight: '300px', overflowY: 'auto', fontFamily: 'monospace', fontSize: '12px', lineHeight: '1.8', color: '#333' }}>
                {logLines.map((line, i) => <div key={i}>{line}</div>)}
              </div>
            </details>
          )}

          {/* Findings Table */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ margin: 0, color: '#0f3460' }}>Findings ({findingsTotal})</h3>
              <div style={{ display: 'flex', gap: '6px' }}>
                {['', 'critical', 'high', 'medium', 'low', 'info'].map(s => (
                  <button key={s} onClick={() => setSevFilter(s)} style={{
                    padding: '4px 12px', borderRadius: '14px', fontSize: '11px', fontWeight: sevFilter === s ? 600 : 400,
                    border: sevFilter === s ? '2px solid #0f3460' : '1px solid #ccc',
                    background: sevFilter === s ? '#e8f0fe' : '#fff', color: sevFilter === s ? '#0f3460' : '#666', cursor: 'pointer',
                    textTransform: 'capitalize',
                  }}>{s || 'All'}</button>
                ))}
              </div>
            </div>
            {findings.length > 0 ? (
              <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
                      <th style={{ padding: '10px' }}>Severity</th>
                      <th style={{ padding: '10px' }}>Title</th>
                      <th style={{ padding: '10px' }}>File</th>
                      <th style={{ padding: '10px' }}>Line</th>
                      <th style={{ padding: '10px' }}>Source</th>
                      <th style={{ padding: '10px' }}>CWE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {findings.map(f => (
                      <>
                        <tr key={f.id} onClick={() => loadFullFinding(f.id)} style={{ borderBottom: '1px solid #f0f0f0', cursor: 'pointer', background: expandedFinding === f.id ? '#f8f9ff' : 'transparent' }}>
                          <td style={{ padding: '10px' }}>
                            <span style={{ background: severityColors[f.severity] || '#6c757d', color: '#fff', padding: '2px 8px', borderRadius: '10px', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase' }}>{f.severity}</span>
                          </td>
                          <td style={{ padding: '10px', fontWeight: 500 }}>{f.title}</td>
                          <td style={{ padding: '10px', fontFamily: 'monospace', fontSize: '11px', color: '#0f3460' }}>{f.file_path}</td>
                          <td style={{ padding: '10px', fontSize: '12px' }}>{f.start_line}{f.end_line > f.start_line ? `-${f.end_line}` : ''}</td>
                          <td style={{ padding: '10px', fontSize: '12px', color: '#666' }}>{f.source}</td>
                          <td style={{ padding: '10px', fontSize: '12px' }}>{f.cwe || '—'}</td>
                        </tr>
                        {expandedFinding === f.id && (
                          <tr key={`${f.id}-detail`}>
                            <td colSpan={6} style={{ padding: '0 10px 16px 10px', background: '#f8f9ff' }}>
                              <div style={{ padding: '12px 16px', borderRadius: '6px', background: '#fff', border: '1px solid #e9ecef' }}>
                                <div style={{ marginBottom: '10px' }}>
                                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#333', marginBottom: '4px' }}>Explanation</div>
                                  <div style={{ fontSize: '13px', color: '#555', whiteSpace: 'pre-wrap' }}>{(expandedDetail || f).explanation || '—'}</div>
                                </div>
                                <div>
                                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#333', marginBottom: '4px' }}>Recommendation</div>
                                  <div style={{ fontSize: '13px', color: '#555', whiteSpace: 'pre-wrap' }}>{(expandedDetail || f).recommendation || '—'}</div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ ...cardStyle, textAlign: 'center', color: '#999' }}>
                {exec.finding_count > 0 ? 'Findings data not stored for this execution.' : 'No findings.'}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Executive Summary Tab */}
      {tab === 'executive' && (
        <div>
          {/* Metrics */}
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '24px' }}>
            <MetricBox label="Total Findings" value={exec.finding_count} />
            <MetricBox label="Gate Status" value={(exec.quality_gate_status || '—').toUpperCase()} color={exec.quality_gate_status === 'pass' ? '#28a745' : '#dc3545'} />
            <MetricBox label="Duration" value={(exec.duration_seconds ?? 0) > 0 ? `${(exec.duration_seconds ?? 0).toFixed(0)}s` : '—'} />
            <MetricBox label="Cost" value={`$${(exec.cost_usd ?? 0).toFixed(4)}`} />
            <MetricBox label="Status" value={exec.status.toUpperCase()} color={sc.fg} />
          </div>

          {/* Severity Distribution */}
          {sevEntries.length > 0 && (
            <div style={{ ...cardStyle, marginBottom: '20px' }}>
              <h4 style={{ marginTop: 0, marginBottom: '14px', color: '#0f3460' }}>Severity Distribution</h4>
              {sevEntries.map(([sev, count]) => {
                const pct = totalSev > 0 ? (count / totalSev) * 100 : 0;
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
              })}
            </div>
          )}

          {/* Executive Download */}
          {(exec.executive_json_path || exec.executive_pdf_path) && (
            <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
              {exec.executive_json_path && <DownloadBtn label="Executive Summary (JSON)" onClick={() => download('executive-json')} />}
              {exec.executive_pdf_path && <DownloadBtn label="Executive Summary (PDF)" onClick={() => download('executive-pdf')} />}
            </div>
          )}

          {/* Top Critical/High Findings */}
          {findings.filter(f => f.severity === 'critical' || f.severity === 'high').length > 0 && (
            <div style={cardStyle}>
              <h4 style={{ marginTop: 0, marginBottom: '14px', color: '#0f3460' }}>Key Findings (Critical &amp; High)</h4>
              {findings.filter(f => f.severity === 'critical' || f.severity === 'high').slice(0, 10).map(f => (
                <div key={f.id} style={{ padding: '10px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span style={{ background: severityColors[f.severity], color: '#fff', padding: '1px 6px', borderRadius: '8px', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase' }}>{f.severity}</span>
                    <span style={{ fontWeight: 600, fontSize: '13px' }}>{f.title}</span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#666' }}>
                    <code>{f.file_path}:{f.start_line}</code>
                    {f.explanation && <span style={{ marginLeft: '12px' }}>{f.explanation.slice(0, 150)}{f.explanation.length > 150 ? '...' : ''}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Failed State Info */}
          {(isFailed || isIncomplete) && (
            <div style={{ ...cardStyle, background: '#fff3f3', border: '1px solid #f5c2c7' }}>
              <h4 style={{ marginTop: 0, color: '#dc3545' }}>Execution {isFailed ? 'Failed' : 'Incomplete'}</h4>
              {exec.error_message && <div style={{ fontSize: '13px', fontFamily: 'monospace', whiteSpace: 'pre-wrap', color: '#842029', marginBottom: '8px' }}>{exec.error_message}</div>}
              {lastStep && <div style={{ fontSize: '12px', color: '#666' }}>Last step reached: <strong>{lastStep}</strong></div>}
              {logLines.length > 0 && (
                <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                  Completed {logLines.length} of ~15 execution phases before stopping.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MetricBox({ label, value, color = '#0f3460' }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #dee2e6', borderRadius: '8px', padding: '16px 24px', textAlign: 'center', minWidth: '130px' }}>
      <div style={{ fontSize: '24px', fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: '11px', color: '#6c757d', textTransform: 'uppercase', marginTop: '4px' }}>{label}</div>
    </div>
  );
}

function DownloadBtn({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      padding: '8px 16px', border: '1px solid #0f3460', borderRadius: '6px',
      background: '#fff', color: '#0f3460', cursor: 'pointer', fontWeight: 600, fontSize: '13px',
    }}>{label}</button>
  );
}
