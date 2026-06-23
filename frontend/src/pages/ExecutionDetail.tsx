import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchApi } from '../hooks/useApi';
import { QAExecution, QAFinding } from '../types';

type TabKey = 'findings' | 'full' | 'executive';

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
const card: React.CSSProperties = { background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', padding: '20px', marginBottom: '20px' };
const sectionTitle: React.CSSProperties = { marginTop: 0, marginBottom: '14px', color: '#0f3460', fontSize: '16px' };

/* eslint-disable @typescript-eslint/no-explicit-any */
interface ReportData {
  report_metadata?: any;
  repository_context?: any;
  executive_summary?: any;
  scope_summary?: any;
  findings?: any[];
  finding_clusters?: any[];
  resolved_issues?: any[];
  positive_observations?: any[];
  suppressed_findings?: any[];
  appendix?: any;
}

export function ExecutionDetail() {
  const { id } = useParams<{ id: string }>();
  const [exec, setExec] = useState<QAExecution | null>(null);
  const [findings, setFindings] = useState<QAFinding[]>([]);
  const [findingsTotal, setFindingsTotal] = useState(0);
  const [report, setReport] = useState<ReportData | null>(null);
  const [execReport, setExecReport] = useState<Record<string, any> | null>(null);
  const [tab, setTab] = useState<TabKey>('findings');
  const [loading, setLoading] = useState(true);
  const [sevFilter, setSevFilter] = useState('');
  const [expandedFinding, setExpandedFinding] = useState<string | null>(null);
  const [expandedDetail, setExpandedDetail] = useState<QAFinding | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchApi<QAExecution>(`/api/qa/executions/${id}`)
      .then(setExec).catch(() => {}).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const url = sevFilter ? `/api/reports/${id}/findings?limit=200&severity=${sevFilter}` : `/api/reports/${id}/findings?limit=200`;
    fetchApi<{ items: QAFinding[]; total: number }>(url)
      .then(d => { setFindings(d.items); setFindingsTotal(d.total); }).catch(() => {});
  }, [id, sevFilter]);

  useEffect(() => {
    if (!id) return;
    fetchApi<ReportData>(`/api/reports/${id}/content/full`).then(setReport).catch(() => {});
    fetchApi<Record<string, any>>(`/api/reports/${id}/content/executive`).then(setExecReport).catch(() => {});
  }, [id]);

  const loadFullFinding = (fid: string) => {
    if (expandedFinding === fid) { setExpandedFinding(null); setExpandedDetail(null); return; }
    setExpandedFinding(fid);
    fetchApi<QAFinding>(`/api/reports/${id}/findings/${fid}`).then(setExpandedDetail).catch(() => setExpandedDetail(null));
  };

  if (loading) return <div><p style={{ color: '#999' }}>Loading...</p></div>;
  if (!exec) return <div><p style={{ color: '#dc3545' }}>Execution not found.</p><Link to="/qa-execution" style={{ color: '#0f3460' }}>Back</Link></div>;

  const repoName = exec.repository_url.replace(/\.git$/, '').split('/').slice(-2).join('/');
  const isFailed = exec.status === 'failed';
  const isIncomplete = exec.status === 'cancelled';
  const sc = statusColors[exec.status] || statusColors.pending;
  const logLines = (exec.execution_log || '').split('\n').filter(Boolean);
  const lastStep = logLines.length > 0 ? logLines[logLines.length - 1] : null;

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
      <div style={{ fontSize: '13px', color: '#666', marginBottom: '16px' }}>
        <Link to="/qa-execution" style={{ color: '#0f3460', textDecoration: 'none' }}>QA Execution</Link>
        <span style={{ margin: '0 8px' }}>/</span>
        <span>{exec.scan_id || exec.id.slice(0, 8)}</span>
      </div>

      {/* Header */}
      <div style={{ ...card, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
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
          <div style={{ fontWeight: 700, color: '#dc3545', marginBottom: '6px' }}>{isFailed ? 'Execution Failed' : 'Execution Incomplete'}</div>
          {exec.error_message && <div style={{ fontSize: '13px', color: '#842029', marginBottom: '8px', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>{exec.error_message}</div>}
          {lastStep && <div style={{ fontSize: '12px', color: '#666' }}>Last completed step: <strong>{lastStep}</strong></div>}
          {logLines.length === 0 && !exec.error_message && <div style={{ fontSize: '13px', color: '#999' }}>No execution details available.</div>}
        </div>
      )}

      {/* Downloads */}
      {hasReports && (
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
          {exec.report_json_path && <DlBtn label="Full Report (JSON)" onClick={() => download('full-json')} />}
          {exec.report_pdf_path && <DlBtn label="Full Report (PDF)" onClick={() => download('full-pdf')} />}
          {exec.executive_json_path && <DlBtn label="Executive (JSON)" onClick={() => download('executive-json')} />}
          {exec.executive_pdf_path && <DlBtn label="Executive (PDF)" onClick={() => download('executive-pdf')} />}
        </div>
      )}

      {/* Tab Bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid #dee2e6', marginBottom: '20px', gap: '4px' }}>
        {tabBtn('findings', 'Findings')}
        {tabBtn('full', 'Full Audit Report')}
        {tabBtn('executive', 'Executive Summary')}
      </div>

      {/* ===== FINDINGS TAB ===== */}
      {tab === 'findings' && (
        <div>
          {/* Severity filter */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ margin: 0, color: '#0f3460' }}>Findings ({findingsTotal})</h3>
            <div style={{ display: 'flex', gap: '6px' }}>
              {['', 'critical', 'high', 'medium', 'low', 'info'].map(s => (
                <button key={s} onClick={() => setSevFilter(s)} style={{
                  padding: '4px 12px', borderRadius: '14px', fontSize: '11px', fontWeight: sevFilter === s ? 600 : 400,
                  border: sevFilter === s ? '2px solid #0f3460' : '1px solid #ccc',
                  background: sevFilter === s ? '#e8f0fe' : '#fff', color: sevFilter === s ? '#0f3460' : '#666',
                  cursor: 'pointer', textTransform: 'capitalize',
                }}>{s || 'All'}</button>
              ))}
            </div>
          </div>

          {findings.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {findings.map(f => {
                const isOpen = expandedFinding === f.id;
                const detail = isOpen ? (expandedDetail || f) : f;
                return (
                  <div key={f.id} style={{ ...card, marginBottom: 0, borderLeft: `4px solid ${severityColors[f.severity] || '#6c757d'}`, cursor: 'pointer' }} onClick={() => loadFullFinding(f.id)}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: isOpen ? '12px' : 0 }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <span style={{ background: severityColors[f.severity] || '#6c757d', color: '#fff', padding: '2px 8px', borderRadius: '10px', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase' }}>{f.severity}</span>
                          <span style={{ fontWeight: 600, fontSize: '14px', color: '#333' }}>{f.title}</span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#666', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                          <span><code style={{ color: '#0f3460' }}>{f.file_path}:{f.start_line}{f.end_line > f.start_line ? `-${f.end_line}` : ''}</code></span>
                          <span>Source: {f.source}</span>
                          <span>Tier: {f.tier}</span>
                          {f.cwe && <span>CWE: {f.cwe}</span>}
                          <span>Confidence: {f.confidence}</span>
                        </div>
                      </div>
                      <span style={{ fontSize: '11px', color: '#999', transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>&#9654;</span>
                    </div>

                    {isOpen && (
                      <div style={{ marginTop: '8px' }}>
                        <div style={{ background: '#f8f9fa', borderRadius: '6px', padding: '14px 16px', marginBottom: '10px' }}>
                          <div style={{ fontSize: '12px', fontWeight: 600, color: '#0f3460', marginBottom: '6px' }}>Explanation</div>
                          <div style={{ fontSize: '13px', color: '#333', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{detail.explanation || 'No explanation available.'}</div>
                        </div>
                        <div style={{ background: '#eef6ee', borderRadius: '6px', padding: '14px 16px' }}>
                          <div style={{ fontSize: '12px', fontWeight: 600, color: '#198754', marginBottom: '6px' }}>Recommendation</div>
                          <div style={{ fontSize: '13px', color: '#333', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{detail.recommendation || 'No recommendation available.'}</div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ ...card, textAlign: 'center', color: '#999' }}>
              {exec.finding_count > 0 ? 'Findings data not stored for this execution. Run a new scan to populate.' : 'No findings reported.'}
            </div>
          )}
        </div>
      )}

      {/* ===== FULL AUDIT REPORT TAB ===== */}
      {tab === 'full' && (
        <div>
          {report ? <FullReportViewer report={report} /> : (
            <div style={{ ...card, textAlign: 'center', color: '#999' }}>
              {isFailed ? 'Report not available — execution failed before report generation.' : 'Loading report...'}
            </div>
          )}

          {logLines.length > 0 && (
            <details style={{ marginBottom: '20px' }}>
              <summary style={{ cursor: 'pointer', fontSize: '14px', fontWeight: 600, color: '#0f3460', padding: '10px 0' }}>Execution Log ({logLines.length} entries)</summary>
              <div style={{ ...card, maxHeight: '300px', overflowY: 'auto', fontFamily: 'monospace', fontSize: '12px', lineHeight: '1.8', color: '#333' }}>
                {logLines.map((l, i) => <div key={i}>{l}</div>)}
              </div>
            </details>
          )}
        </div>
      )}

      {/* ===== EXECUTIVE SUMMARY TAB ===== */}
      {tab === 'executive' && (
        <div>
          {execReport ? <ExecutiveReportViewer report={execReport} /> : (
            <div>
              {/* Fallback to execution data */}
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '24px' }}>
                <MBox label="Total Findings" value={exec.finding_count} />
                <MBox label="Gate Status" value={(exec.quality_gate_status || '—').toUpperCase()} color={exec.quality_gate_status === 'pass' ? '#28a745' : '#dc3545'} />
                <MBox label="Duration" value={(exec.duration_seconds ?? 0) > 0 ? `${(exec.duration_seconds ?? 0).toFixed(0)}s` : '—'} />
                <MBox label="Cost" value={`$${(exec.cost_usd ?? 0).toFixed(4)}`} />
              </div>
              <div style={{ ...card, textAlign: 'center', color: '#999' }}>Executive report not available.</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ===== Full Report Viewer ===== */
function FullReportViewer({ report }: { report: ReportData }) {
  const meta = report.report_metadata || {};
  const repo = report.repository_context || {};
  const scope = report.scope_summary || {};
  const exec = report.executive_summary || {};
  const allFindings = report.findings || [];
  const clusters = report.finding_clusters || [];
  const resolved = report.resolved_issues || [];
  const positive = report.positive_observations || [];
  const suppressed = report.suppressed_findings || [];

  const sevCounts = exec.finding_counts_by_severity || {};
  const catCounts = exec.finding_counts_by_category || {};
  const sevEntries = Object.entries(sevCounts as Record<string, number>).filter(([, v]) => v > 0);
  const totalSev = sevEntries.reduce((s, [, v]) => s + v, 0);

  return (
    <div>
      {/* Report Header */}
      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h3 style={sectionTitle}>Report: {meta.report_id}</h3>
            <div style={{ fontSize: '13px', color: '#666', lineHeight: '1.8' }}>
              <div>Repository: <strong>{repo.repository || repo.repository_url}</strong></div>
              {repo.branch && <div>Branch: <code>{repo.branch}</code>{repo.commit_sha && <span> @ <code>{repo.commit_sha.slice(0, 7)}</code></span>}</div>}
              {repo.pr_number && <div>PR: #{repo.pr_number} {repo.pr_title && `— ${repo.pr_title}`}</div>}
              <div>Trigger: {meta.trigger} | Platform: v{meta.platform_version}</div>
            </div>
          </div>
          <div style={{ textAlign: 'right', fontSize: '12px', color: '#666' }}>
            <div>Generated: {meta.generated_at ? new Date(meta.generated_at).toLocaleString() : '—'}</div>
            <div>Duration: {(meta.execution_duration_seconds ?? 0).toFixed(0)}s</div>
            <div>Cost: ${(meta.execution_cost_usd ?? 0).toFixed(4)}</div>
          </div>
        </div>
      </div>

      {/* Verdict & Gate */}
      <div style={{ ...card, borderLeft: `4px solid ${exec.quality_gate_status === 'pass' ? '#28a745' : '#dc3545'}` }}>
        <h4 style={sectionTitle}>Quality Gate: <span style={{ color: exec.quality_gate_status === 'pass' ? '#28a745' : '#dc3545', textTransform: 'uppercase' }}>{exec.quality_gate_status || '—'}</span></h4>
        {exec.verdict && <div style={{ fontSize: '14px', color: '#333', lineHeight: '1.6' }}>{exec.verdict}</div>}
        <div style={{ fontSize: '13px', color: '#666', marginTop: '8px' }}>
          Risk Level: <strong style={{ textTransform: 'uppercase' }}>{exec.risk_level || '—'}</strong>
          {exec.resolved_count > 0 && <span style={{ marginLeft: '16px' }}>Resolved: {exec.resolved_count}</span>}
          {exec.positive_observations_count > 0 && <span style={{ marginLeft: '16px' }}>Positive: {exec.positive_observations_count}</span>}
        </div>
      </div>

      {/* Scope */}
      <div style={card}>
        <h4 style={sectionTitle}>Scope</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px', fontSize: '13px' }}>
          <div>Files Analyzed: <strong>{scope.files_analyzed ?? 0}</strong></div>
          <div>Files Skipped: <strong>{scope.files_skipped ?? 0}</strong></div>
          <div>Tiers: <strong>{(scope.tiers_executed || []).join(', ') || '—'}</strong></div>
          <div>Agents: <strong>{(scope.agents_used || []).length || 0}</strong></div>
          {scope.diff_mode && <div>Mode: <strong>Diff ({scope.lines_changed ?? 0} lines)</strong></div>}
        </div>
      </div>

      {/* Severity Distribution */}
      {sevEntries.length > 0 && (
        <div style={card}>
          <h4 style={sectionTitle}>Severity Distribution</h4>
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

      {/* Category Breakdown */}
      {Object.keys(catCounts).length > 0 && (
        <div style={card}>
          <h4 style={sectionTitle}>Findings by Category</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '13px' }}>
            {Object.entries(catCounts as Record<string, number>).filter(([, v]) => v > 0).sort(([, a], [, b]) => b - a).map(([cat, count]) => (
              <div key={cat} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #f0f0f0' }}>
                <span style={{ textTransform: 'capitalize' }}>{cat.replace(/_/g, ' ')}</span>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Findings */}
      {allFindings.length > 0 && (
        <div style={card}>
          <h4 style={sectionTitle}>All Findings ({allFindings.length})</h4>
          {allFindings.map((f: any, i: number) => {
            const sev = typeof f.severity === 'number' ? ['info', 'low', 'medium', 'high', 'critical'][f.severity] || 'info' : f.severity;
            return (
              <details key={f.id || i} style={{ marginBottom: '8px', borderBottom: '1px solid #f0f0f0', paddingBottom: '8px' }}>
                <summary style={{ cursor: 'pointer', fontSize: '13px', padding: '6px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ background: severityColors[sev] || '#6c757d', color: '#fff', padding: '1px 6px', borderRadius: '8px', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', flexShrink: 0 }}>{sev}</span>
                  <span style={{ fontWeight: 500 }}>{f.title || 'Untitled finding'}</span>
                  <span style={{ color: '#999', fontSize: '11px', marginLeft: 'auto', flexShrink: 0 }}>{f.file}:{f.start_line}</span>
                </summary>
                <div style={{ padding: '8px 0 4px 20px', fontSize: '13px', color: '#444', lineHeight: '1.6' }}>
                  {f.explanation && <div style={{ marginBottom: '8px' }}><strong style={{ color: '#0f3460' }}>Explanation:</strong><div style={{ whiteSpace: 'pre-wrap', marginTop: '4px' }}>{f.explanation}</div></div>}
                  {f.recommendation && <div style={{ marginBottom: '8px' }}><strong style={{ color: '#198754' }}>Recommendation:</strong><div style={{ whiteSpace: 'pre-wrap', marginTop: '4px' }}>{f.recommendation}</div></div>}
                  <div style={{ fontSize: '11px', color: '#999', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                    <span>Source: {f.source}</span>
                    <span>Category: {f.category}</span>
                    {f.cwe && <span>CWE: {f.cwe}</span>}
                    <span>Confidence: {f.confidence}</span>
                    {f.id && <span>ID: {f.id}</span>}
                  </div>
                </div>
              </details>
            );
          })}
        </div>
      )}

      {/* Finding Clusters */}
      {clusters.length > 0 && (
        <div style={card}>
          <h4 style={sectionTitle}>Finding Clusters</h4>
          {clusters.map((c: any, i: number) => (
            <div key={i} style={{ marginBottom: '10px', padding: '10px', background: '#f8f9fa', borderRadius: '6px' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>{c.name || c.pattern || `Cluster ${i + 1}`}</div>
              <div style={{ fontSize: '12px', color: '#666' }}>{c.description || `${c.finding_count || c.findings?.length || 0} related findings`}</div>
            </div>
          ))}
        </div>
      )}

      {/* Positive Observations */}
      {positive.length > 0 && (
        <div style={{ ...card, borderLeft: '4px solid #28a745' }}>
          <h4 style={sectionTitle}>Positive Observations ({positive.length})</h4>
          {positive.map((p: any, i: number) => (
            <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0', fontSize: '13px' }}>
              <div style={{ fontWeight: 500 }}>{p.title || p.observation}</div>
              {p.explanation && <div style={{ color: '#666', marginTop: '2px' }}>{p.explanation}</div>}
            </div>
          ))}
        </div>
      )}

      {/* Resolved Issues */}
      {resolved.length > 0 && (
        <div style={card}>
          <h4 style={sectionTitle}>Resolved Issues ({resolved.length})</h4>
          {resolved.map((r: any, i: number) => (
            <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid #f0f0f0', fontSize: '13px', color: '#666' }}>
              {r.title || r.description || JSON.stringify(r).slice(0, 100)}
            </div>
          ))}
        </div>
      )}

      {/* Suppressed */}
      {suppressed.length > 0 && (
        <details style={{ marginBottom: '20px' }}>
          <summary style={{ cursor: 'pointer', fontSize: '14px', fontWeight: 600, color: '#6c757d', padding: '10px 0' }}>Suppressed Findings ({suppressed.length})</summary>
          <div style={card}>
            {suppressed.map((s: any, i: number) => (
              <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid #f0f0f0', fontSize: '12px', color: '#999' }}>
                [{s.severity}] {s.title || 'Untitled'} — {s.file}:{s.start_line} — Reason: {s.suppression_reason || s.classification || 'suppressed'}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

/* ===== Executive Report Viewer ===== */
function ExecutiveReportViewer({ report }: { report: Record<string, any> }) {
  const risk = report.risk || report.risk_level || '—';
  const total = report.total ?? report.actionable ?? 0;
  const mustFix = report.must_fix_count ?? 0;
  const shouldFix = report.should_fix_count ?? 0;
  const consider = report.consider_count ?? 0;
  const noiseRemoved = report.noise_removed ?? 0;
  const items = report.items || [];
  const categories = report.categories || {};

  return (
    <div>
      {/* Executive Metrics */}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '24px' }}>
        <MBox label="Risk Level" value={risk} color={risk === 'CRITICAL' || risk === 'HIGH' ? '#dc3545' : risk === 'MEDIUM' ? '#fd7e14' : '#28a745'} />
        <MBox label="Total Actionable" value={total} />
        <MBox label="Must Fix" value={mustFix} color="#dc3545" />
        <MBox label="Should Fix" value={shouldFix} color="#fd7e14" />
        <MBox label="Consider" value={consider} color="#0d6efd" />
        <MBox label="Noise Removed" value={noiseRemoved} color="#6c757d" />
      </div>

      {/* Categories */}
      {Object.keys(categories).length > 0 && (
        <div style={card}>
          <h4 style={sectionTitle}>Categories</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '13px' }}>
            {Object.entries(categories as Record<string, number>).filter(([, v]) => v > 0).sort(([, a], [, b]) => (b as number) - (a as number)).map(([cat, count]) => (
              <div key={cat} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #f0f0f0' }}>
                <span style={{ textTransform: 'capitalize' }}>{cat.replace(/_/g, ' ')}</span>
                <strong>{count as number}</strong>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Items */}
      {items.length > 0 && (
        <div style={card}>
          <h4 style={sectionTitle}>Action Items ({items.length})</h4>
          {items.map((item: any, i: number) => (
            <div key={i} style={{ padding: '10px 0', borderBottom: '1px solid #f0f0f0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <span style={{ background: severityColors[item.severity] || '#6c757d', color: '#fff', padding: '1px 6px', borderRadius: '8px', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase' }}>{item.severity || '—'}</span>
                <span style={{ fontWeight: 600, fontSize: '13px' }}>{item.title || 'Untitled'}</span>
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>
                {item.file && <code>{item.file}:{item.line || item.start_line}</code>}
                {item.action && <span style={{ marginLeft: '12px' }}>{item.action}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Exclusion Reasons */}
      {report.exclusion_reasons && Object.keys(report.exclusion_reasons).length > 0 && (
        <details>
          <summary style={{ cursor: 'pointer', fontSize: '14px', fontWeight: 600, color: '#6c757d', padding: '10px 0' }}>Exclusion Reasons</summary>
          <div style={{ ...card, fontSize: '13px' }}>
            {Object.entries(report.exclusion_reasons as Record<string, number>).map(([reason, count]) => (
              <div key={reason} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
                <span>{reason}</span><strong>{count as number}</strong>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function MBox({ label, value, color = '#0f3460' }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #dee2e6', borderRadius: '8px', padding: '16px 24px', textAlign: 'center', minWidth: '130px' }}>
      <div style={{ fontSize: '24px', fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: '11px', color: '#6c757d', textTransform: 'uppercase', marginTop: '4px' }}>{label}</div>
    </div>
  );
}

function DlBtn({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      padding: '8px 16px', border: '1px solid #0f3460', borderRadius: '6px',
      background: '#fff', color: '#0f3460', cursor: 'pointer', fontWeight: 600, fontSize: '13px',
    }}>{label}</button>
  );
}
