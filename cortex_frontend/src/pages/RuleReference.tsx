import { useState } from 'react';
import { TOOL_INFO, COMMON_CWES, getRuleUrl, getCweUrl } from '../data/ruleReference';

type CategoryFilter = '' | 'security' | 'correctness' | 'design' | 'hygiene' | 'consistency';

const categoryColors: Record<string, { bg: string; fg: string }> = {
  security: { bg: '#f8d7da', fg: '#dc3545' },
  correctness: { bg: '#cfe2ff', fg: '#0d6efd' },
  design: { bg: '#d1e7dd', fg: '#198754' },
  hygiene: { bg: '#fff3cd', fg: '#856404' },
  consistency: { bg: '#e2e3e5', fg: '#495057' },
};

const card: React.CSSProperties = {
  background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', padding: '20px', marginBottom: '16px',
};

export function RuleReference() {
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('');
  const [expandedTool, setExpandedTool] = useState<string | null>(null);

  const tools = Object.entries(TOOL_INFO);
  const searchLower = search.toLowerCase();

  const filteredTools = tools.filter(([key, info]) => {
    if (categoryFilter && info.category !== categoryFilter) return false;
    if (search) {
      const matchesName = info.displayName.toLowerCase().includes(searchLower) || key.includes(searchLower);
      const matchesRule = info.sampleRules.some(r => r.toLowerCase().includes(searchLower));
      const matchesPrefix = info.rulePrefix.toLowerCase().includes(searchLower);
      const matchesDesc = info.description.toLowerCase().includes(searchLower);
      return matchesName || matchesRule || matchesPrefix || matchesDesc;
    }
    return true;
  });

  const matchedCwes = search
    ? COMMON_CWES.filter(c => c.id.toLowerCase().includes(searchLower) || c.name.toLowerCase().includes(searchLower))
    : [];

  return (
    <div>
      <h2 style={{ marginBottom: '8px' }}>Rule Reference</h2>
      <p style={{ color: '#666', fontSize: '14px', marginBottom: '20px' }}>
        Documentation for all QA scanning tools, rule IDs, and security standards used by the platform.
      </p>

      {/* Search + Filter */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search rule ID, tool name, or keyword (e.g. B108, eval, XSS)..."
          style={{ flex: 1, minWidth: '250px', padding: '10px 14px', border: '1px solid #dee2e6', borderRadius: '6px', fontSize: '14px' }}
        />
        <div style={{ display: 'flex', gap: '6px' }}>
          {(['', 'security', 'correctness', 'design', 'hygiene', 'consistency'] as const).map(cat => {
            const active = categoryFilter === cat;
            const colors = cat ? categoryColors[cat] : { bg: '#f0f0f0', fg: '#333' };
            return (
              <button key={cat} onClick={() => setCategoryFilter(cat)} style={{
                padding: '6px 14px', borderRadius: '16px', fontSize: '12px', fontWeight: active ? 600 : 400,
                border: active ? '2px solid ' + colors.fg : '1px solid #ccc',
                background: active ? colors.bg : '#fff', color: active ? colors.fg : '#666',
                cursor: 'pointer', textTransform: 'capitalize',
              }}>{cat || 'All'}</button>
            );
          })}
        </div>
      </div>

      {/* CWE Search Results */}
      {matchedCwes.length > 0 && (
        <div style={{ ...card, borderLeft: '4px solid #dc3545' }}>
          <h3 style={{ marginTop: 0, marginBottom: '12px', color: '#0f3460', fontSize: '16px' }}>CWE Matches</h3>
          {matchedCwes.map(c => (
            <div key={c.id} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <a href={getCweUrl(c.id)} target="_blank" rel="noopener noreferrer" style={{ color: '#0f3460', fontWeight: 700, textDecoration: 'none', fontFamily: 'monospace' }}>{c.id}</a>
                <span style={{ marginLeft: '10px', fontWeight: 500 }}>{c.name}</span>
                <div style={{ fontSize: '12px', color: '#666', marginTop: '2px' }}>{c.description}</div>
              </div>
              <a href={getCweUrl(c.id)} target="_blank" rel="noopener noreferrer" style={{ color: '#0f3460', fontSize: '12px', textDecoration: 'none', whiteSpace: 'nowrap' }}>MITRE Docs</a>
            </div>
          ))}
        </div>
      )}

      {/* Tool Cards */}
      <div style={{ marginBottom: '12px', fontSize: '13px', color: '#666' }}>
        {filteredTools.length} of {tools.length} tools
      </div>

      {filteredTools.map(([key, info]) => {
        const isExpanded = expandedTool === key;
        const catColor = categoryColors[info.category] || categoryColors.consistency;
        return (
          <div key={key} style={{ ...card, borderLeft: `4px solid ${catColor.fg}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', cursor: 'pointer' }}
              onClick={() => setExpandedTool(isExpanded ? null : key)}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 700, fontSize: '16px', color: '#0f3460' }}>{info.displayName}</span>
                  <span style={{ background: catColor.bg, color: catColor.fg, padding: '2px 8px', borderRadius: '10px', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase' }}>{info.category}</span>
                  {info.rulePrefix && <span style={{ background: '#f4f4f4', padding: '2px 6px', borderRadius: '3px', fontSize: '11px', fontFamily: 'monospace', color: '#666' }}>{info.rulePrefix}</span>}
                </div>
                <div style={{ fontSize: '13px', color: '#555' }}>{info.description}</div>
              </div>
              <span style={{ fontSize: '11px', color: '#999', transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s', marginLeft: '12px', flexShrink: 0 }}>&#9654;</span>
            </div>

            {isExpanded && (
              <div style={{ marginTop: '16px', borderTop: '1px solid #e9ecef', paddingTop: '16px' }}>
                {info.docUrl && (
                  <div style={{ marginBottom: '12px' }}>
                    <span style={{ fontSize: '12px', color: '#999' }}>Documentation: </span>
                    <a href={info.docUrl} target="_blank" rel="noopener noreferrer" style={{ color: '#0f3460', fontSize: '13px' }}>{info.docUrl}</a>
                  </div>
                )}

                {info.rulePrefix && (
                  <div style={{ marginBottom: '12px' }}>
                    <span style={{ fontSize: '12px', color: '#999' }}>Rule ID format: </span>
                    <code style={{ background: '#f4f4f4', padding: '2px 6px', borderRadius: '3px', fontSize: '12px' }}>{info.rulePrefix}xxx</code>
                  </div>
                )}

                {info.sampleRules.length > 0 && (
                  <div>
                    <div style={{ fontSize: '12px', color: '#999', marginBottom: '8px' }}>Sample rules:</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {info.sampleRules.map((rule, i) => {
                        const ruleId = rule.split(' ')[0];
                        const ruleDesc = rule.slice(ruleId.length).trim();
                        const url = getRuleUrl(key, ruleId);
                        return (
                          <div key={i} style={{ background: '#f8f9fa', border: '1px solid #e9ecef', borderRadius: '6px', padding: '6px 10px', fontSize: '12px' }}>
                            {url ? (
                              <a href={url} target="_blank" rel="noopener noreferrer" style={{ color: '#0f3460', fontWeight: 700, fontFamily: 'monospace', textDecoration: 'none' }}>{ruleId}</a>
                            ) : (
                              <span style={{ fontWeight: 700, fontFamily: 'monospace', color: '#333' }}>{ruleId}</span>
                            )}
                            {ruleDesc && <span style={{ color: '#666', marginLeft: '6px' }}>{ruleDesc}</span>}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      {filteredTools.length === 0 && (
        <div style={{ ...card, textAlign: 'center', color: '#999' }}>No tools match your search.</div>
      )}

      {/* CWE Reference Section */}
      {!search && (
        <div style={{ marginTop: '30px' }}>
          <h3 style={{ color: '#0f3460', marginBottom: '12px' }}>Common CWE Reference</h3>
          <p style={{ fontSize: '13px', color: '#666', marginBottom: '16px' }}>
            Common Weakness Enumeration (CWE) IDs referenced by security findings. Maintained by MITRE.
          </p>
          <div style={card}>
            {COMMON_CWES.map(c => (
              <div key={c.id} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                <a href={getCweUrl(c.id)} target="_blank" rel="noopener noreferrer" style={{ color: '#0f3460', fontWeight: 700, textDecoration: 'none', fontFamily: 'monospace', marginRight: '10px' }}>{c.id}</a>
                <span style={{ fontWeight: 500 }}>{c.name}</span>
                <div style={{ fontSize: '12px', color: '#666', marginTop: '2px', marginLeft: '80px' }}>{c.description}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
