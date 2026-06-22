import { useEffect, useState } from 'react';
import { fetchApi } from '../hooks/useApi';
import { AppSettings } from '../types';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface AutomationRule {
  id: string;
  name: string;
  trigger: string;
  active: boolean;
}

interface GitHubSettings {
  token: string;
  api_url: string;
  org_name: string;
  configured: boolean;
}

interface OrgRepo {
  owner: string;
  repo_name: string;
  full_name: string;
  description: string;
  default_branch: string;
  html_url: string;
  language: string;
  private: boolean;
  stars: number;
  already_added: boolean;
}


interface Repository {
  id: string;
  owner: string;
  repo_name: string;
  description: string;
  default_branch: string;
  auto_fetch: boolean;
  qa_tiers: string;
  active: boolean;
}

/* ------------------------------------------------------------------ */
/*  Shared styles                                                      */
/* ------------------------------------------------------------------ */

const cardStyle: React.CSSProperties = {
  background: '#fff',
  borderRadius: '8px',
  border: '1px solid #dee2e6',
  padding: '24px',
  marginBottom: '24px',
};

const headingStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: '20px',
  color: '#0f3460',
  fontSize: '18px',
  borderBottom: '2px solid #e9ecef',
  paddingBottom: '10px',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '13px',
  fontWeight: 600,
  marginBottom: '4px',
  color: '#333',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  border: '1px solid #dee2e6',
  borderRadius: '4px',
  fontSize: '14px',
  boxSizing: 'border-box',
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  background: '#fff',
};

const buttonStyle: React.CSSProperties = {
  padding: '8px 20px',
  background: '#0f3460',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 600,
  fontSize: '13px',
};

const dangerButtonStyle: React.CSSProperties = {
  ...buttonStyle,
  background: '#dc3545',
  padding: '4px 12px',
  fontSize: '12px',
};

const fieldGroupStyle: React.CSSProperties = {
  marginBottom: '14px',
};

const statusBadge = (configured: boolean): React.CSSProperties => ({
  display: 'inline-block',
  padding: '3px 10px',
  borderRadius: '12px',
  fontSize: '12px',
  fontWeight: 600,
  background: configured ? '#d4edda' : '#f8d7da',
  color: configured ? '#155724' : '#721c24',
  marginLeft: '12px',
});

const toggleContainerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  marginBottom: '14px',
};

const msgStyle = (msg: string): React.CSSProperties => ({
  fontSize: '13px',
  color: msg.includes('Failed') || msg.includes('Error') ? '#dc3545' : '#28a745',
  marginTop: '8px',
  marginBottom: 0,
});

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function Admin() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);

  // --- GitHub Settings ---
  const [ghToken, setGhToken] = useState('');
  const [ghApiUrl, setGhApiUrl] = useState('https://api.github.com');
  const [ghOrgName, setGhOrgName] = useState('');
  const [orgRepos, setOrgRepos] = useState<OrgRepo[]>([]);
  const [orgRepoSelected, setOrgRepoSelected] = useState<Set<string>>(new Set());
  const [pullingRepos, setPullingRepos] = useState(false);
  const [addingSelected, setAddingSelected] = useState(false);
  const [ghConfigured, setGhConfigured] = useState(false);
  const [ghMsg, setGhMsg] = useState('');

  // --- Linear Settings ---
  const [linearApiKey, setLinearApiKey] = useState('');
  const [linearTeamId, setLinearTeamId] = useState('');
  const [linearWorkspace, setLinearWorkspace] = useState('');
  const [linearAutoCreate, setLinearAutoCreate] = useState(false);
  const [linearMinSeverity, setLinearMinSeverity] = useState('high');
  const [linearMaxTasks, setLinearMaxTasks] = useState(10);
  const [linearConfigured, setLinearConfigured] = useState(false);
  const [linearMsg, setLinearMsg] = useState('');

  // --- Notification Settings ---
  const [slackWebhook, setSlackWebhook] = useState('');
  const [notifEmail, setNotifEmail] = useState('');
  const [notifCritical, setNotifCritical] = useState(true);
  const [notifGateFailure, setNotifGateFailure] = useState(true);
  const [notifConfigured, setNotifConfigured] = useState(false);
  const [notifMsg, setNotifMsg] = useState('');

  // --- Repository Management ---
  const [repos, setRepos] = useState<Repository[]>([]);
  const [repoMsg, setRepoMsg] = useState('');

  // --- Automation Rules ---
  const [rules, setRules] = useState<AutomationRule[]>([]);

  /* ---- Load all data on mount ---- */
  useEffect(() => {
    // Feature toggles / app settings
    fetchApi<AppSettings>('/api/admin/settings')
      .then(data => setSettings(data))
      .catch(() => {})
      .finally(() => setLoading(false));

    // GitHub settings
    fetchApi<GitHubSettings & { org_name?: string; is_configured?: boolean }>('/api/admin/github')
      .then(data => {
        if (data) {
          setGhApiUrl(data.api_url || 'https://api.github.com');
          setGhOrgName(data.org_name || '');
          setGhConfigured(data.configured ?? data.is_configured ?? false);
        }
      })
      .catch(() => {});

    // Linear settings
    fetchApi<Record<string, unknown>>('/api/admin/linear')
      .then(data => {
        if (data) {
          setLinearTeamId((data.team_id as string) || '');
          setLinearWorkspace((data.workspace_name as string) || '');
          setLinearAutoCreate((data.auto_create_tasks as boolean) ?? false);
          setLinearMinSeverity((data.min_severity as string) || 'high');
          setLinearMaxTasks((data.max_tasks_per_scan as number) ?? 10);
          setLinearConfigured((data.is_configured as boolean) ?? false);
        }
      })
      .catch(() => {});

    // Notification settings
    fetchApi<Record<string, unknown>>('/api/admin/notifications')
      .then(data => {
        if (data) {
          setSlackWebhook((data.slack_webhook_url as string) || '');
          setNotifEmail((data.email as string) || '');
          setNotifCritical((data.on_critical as boolean) ?? true);
          setNotifGateFailure((data.on_gate_fail as boolean) ?? true);
          setNotifConfigured((data.is_configured as boolean) ?? false);
        }
      })
      .catch(() => {});

    // Repositories
    fetchApi<{ items: Repository[] }>('/api/github/repos')
      .then(data => setRepos(data.items || []))
      .catch(() => {});

    // Automation rules
    fetchApi<{ items: AutomationRule[] }>('/api/automation/rules')
      .then(data => setRules(data.items || []))
      .catch(() => {});
  }, []);

  /* ---- Handlers ---- */

  const saveGithub = () => {
    setGhMsg('');
    fetchApi('/api/admin/github', {
      method: 'PUT',
      body: JSON.stringify({ token: ghToken || undefined, api_url: ghApiUrl, org_name: ghOrgName }),
    })
      .then(() => {
        setGhMsg('GitHub settings saved.');
        if (ghToken) setGhConfigured(true);
        setGhToken('');
      })
      .catch(() => setGhMsg('Failed to save GitHub settings.'));
  };

  const saveLinear = () => {
    setLinearMsg('');
    fetchApi('/api/admin/linear', {
      method: 'PUT',
      body: JSON.stringify({
        api_key: linearApiKey || undefined,
        team_id: linearTeamId,
        workspace_name: linearWorkspace,
        auto_create_tasks: linearAutoCreate,
        min_severity: linearMinSeverity,
        max_tasks_per_scan: linearMaxTasks,
      }),
    })
      .then(() => {
        setLinearMsg('Linear settings saved.');
        if (linearApiKey) setLinearConfigured(true);
        setLinearApiKey('');
      })
      .catch(() => setLinearMsg('Failed to save Linear settings.'));
  };

  const saveNotifications = () => {
    setNotifMsg('');
    fetchApi('/api/admin/notifications', {
      method: 'PUT',
      body: JSON.stringify({
        slack_webhook_url: slackWebhook,
        email: notifEmail,
        on_critical: notifCritical,
        on_gate_fail: notifGateFailure,
      }),
    })
      .then(() => {
        setNotifMsg('Notification settings saved.');
        setNotifConfigured(true);
      })
      .catch(() => setNotifMsg('Failed to save notification settings.'));
  };

  const deleteRepo = (id: string) => {
    fetchApi(`/api/github/repos/${id}`, { method: 'DELETE' })
      .then(() => setRepos(prev => prev.filter(r => r.id !== id)))
      .catch(() => {});
  };

  const toggleRule = (rule: AutomationRule) => {
    fetchApi(`/api/automation/rules/${rule.id}/toggle`, {
      method: 'PUT',
    })
      .then(() => {
        setRules(prev =>
          prev.map(r => (r.id === rule.id ? { ...r, active: !r.active } : r))
        );
      })
      .catch(() => {});
  };

  /* ---- Render ---- */

  if (loading) {
    return (
      <div>
        <h2 style={{ marginBottom: '20px' }}>Administration</h2>
        <p style={{ color: '#999' }}>Loading settings...</p>
      </div>
    );
  }

  return (
    <div>
      <h2 style={{ marginBottom: '24px' }}>Administration</h2>

      {/* ===== Section 1: GitHub Settings ===== */}
      <div style={cardStyle}>
        <h3 style={headingStyle}>
          GitHub Settings
          <span style={statusBadge(ghConfigured)}>
            {ghConfigured ? 'Configured' : 'Not configured'}
          </span>
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>Token</label>
            <input
              style={inputStyle}
              type="password"
              value={ghToken}
              onChange={e => setGhToken(e.target.value)}
              placeholder={ghConfigured ? '(unchanged -- enter new token to update)' : 'ghp_...'}
            />
          </div>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>API URL</label>
            <input
              style={inputStyle}
              value={ghApiUrl}
              onChange={e => setGhApiUrl(e.target.value)}
              placeholder="https://api.github.com"
            />
          </div>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>Organization / User</label>
            <input
              style={inputStyle}
              value={ghOrgName}
              onChange={e => setGhOrgName(e.target.value)}
              placeholder="e.g. Ruya-AI"
            />
          </div>
        </div>
        <button style={buttonStyle} onClick={saveGithub}>Save GitHub Settings</button>
        {ghMsg && <p style={msgStyle(ghMsg)}>{ghMsg}</p>}
      </div>

      {/* ===== Section 2: Linear Settings ===== */}
      <div style={cardStyle}>
        <h3 style={headingStyle}>
          Linear Settings
          <span style={statusBadge(linearConfigured)}>
            {linearConfigured ? 'Configured' : 'Not configured'}
          </span>
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>API Key</label>
            <input
              style={inputStyle}
              type="password"
              value={linearApiKey}
              onChange={e => setLinearApiKey(e.target.value)}
              placeholder={linearConfigured ? '(unchanged -- enter new key to update)' : 'lin_api_...'}
            />
          </div>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>Team ID</label>
            <input
              style={inputStyle}
              value={linearTeamId}
              onChange={e => setLinearTeamId(e.target.value)}
              placeholder="Team identifier"
            />
          </div>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>Workspace Name</label>
            <input
              style={inputStyle}
              value={linearWorkspace}
              onChange={e => setLinearWorkspace(e.target.value)}
              placeholder="e.g. Engineering"
            />
          </div>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>Min Severity</label>
            <select
              style={selectStyle}
              value={linearMinSeverity}
              onChange={e => setLinearMinSeverity(e.target.value)}
            >
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>Max Tasks Per Scan</label>
            <input
              style={inputStyle}
              type="number"
              min={1}
              value={linearMaxTasks}
              onChange={e => setLinearMaxTasks(Number(e.target.value))}
            />
          </div>
        </div>
        <div style={toggleContainerStyle}>
          <input
            type="checkbox"
            checked={linearAutoCreate}
            onChange={e => setLinearAutoCreate(e.target.checked)}
            id="linear-auto-create"
          />
          <label htmlFor="linear-auto-create" style={{ fontSize: '13px', fontWeight: 500, color: '#333' }}>
            Auto-create tasks from findings
          </label>
        </div>
        <button style={buttonStyle} onClick={saveLinear}>Save Linear Settings</button>
        {linearMsg && <p style={msgStyle(linearMsg)}>{linearMsg}</p>}
      </div>

      {/* ===== Section 3: Notification Settings ===== */}
      <div style={cardStyle}>
        <h3 style={headingStyle}>
          Notification Settings
          <span style={statusBadge(notifConfigured)}>
            {notifConfigured ? 'Configured' : 'Not configured'}
          </span>
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>Slack Webhook URL</label>
            <input
              style={inputStyle}
              value={slackWebhook}
              onChange={e => setSlackWebhook(e.target.value)}
              placeholder="https://hooks.slack.com/services/..."
            />
          </div>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>Email</label>
            <input
              style={inputStyle}
              type="email"
              value={notifEmail}
              onChange={e => setNotifEmail(e.target.value)}
              placeholder="alerts@example.com"
            />
          </div>
        </div>
        <div style={toggleContainerStyle}>
          <input
            type="checkbox"
            checked={notifCritical}
            onChange={e => setNotifCritical(e.target.checked)}
            id="notif-critical"
          />
          <label htmlFor="notif-critical" style={{ fontSize: '13px', fontWeight: 500, color: '#333' }}>
            Notify on critical findings
          </label>
        </div>
        <div style={toggleContainerStyle}>
          <input
            type="checkbox"
            checked={notifGateFailure}
            onChange={e => setNotifGateFailure(e.target.checked)}
            id="notif-gate"
          />
          <label htmlFor="notif-gate" style={{ fontSize: '13px', fontWeight: 500, color: '#333' }}>
            Notify on gate failure
          </label>
        </div>
        <button style={buttonStyle} onClick={saveNotifications}>Save Notification Settings</button>
        {notifMsg && <p style={msgStyle(notifMsg)}>{notifMsg}</p>}
      </div>

      {/* ===== Section 4: Repository Management ===== */}
      <div style={cardStyle}>
        <h3 style={headingStyle}>Repository Management</h3>

        {/* Pull Repositories from GitHub */}
        <div style={{
          background: '#e8f4fd',
          borderRadius: '6px',
          padding: '16px',
          marginBottom: '20px',
          border: '1px solid #b8daff',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: orgRepos.length > 0 ? '14px' : '0' }}>
            <div>
              <h4 style={{ margin: '0 0 4px 0', fontSize: '14px', color: '#0f3460' }}>Pull Repositories from GitHub</h4>
              <p style={{ margin: 0, fontSize: '12px', color: '#666' }}>
                {ghOrgName ? `Fetch all repositories from ${ghOrgName}` : 'Set Organization name in GitHub Settings above first'}
              </p>
            </div>
            <button
              onClick={async () => {
                setPullingRepos(true);
                setOrgRepos([]);
                setOrgRepoSelected(new Set());
                try {
                  const data = await fetchApi<{ repos: OrgRepo[] }>('/api/admin/github/org-repos');
                  setOrgRepos(data.repos);
                } catch (e: unknown) {
                  const msg = e instanceof Error ? e.message : 'Failed to fetch';
                  setRepoMsg(msg);
                }
                setPullingRepos(false);
              }}
              disabled={!ghConfigured || !ghOrgName || pullingRepos}
              style={{
                padding: '8px 20px',
                background: ghConfigured && ghOrgName && !pullingRepos ? '#0f3460' : '#ccc',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: ghConfigured && ghOrgName && !pullingRepos ? 'pointer' : 'default',
                fontWeight: 600,
                fontSize: '13px',
                whiteSpace: 'nowrap',
              }}
            >
              {pullingRepos ? 'Pulling...' : 'Pull Repositories'}
            </button>
          </div>

          {/* Org Repos Selection List */}
          {orgRepos.length > 0 && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '13px', color: '#333', fontWeight: 600 }}>
                  {orgRepos.length} repositories found — select to add for QA
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => {
                      const notAdded = orgRepos.filter(r => !r.already_added).map(r => r.full_name);
                      if (orgRepoSelected.size === notAdded.length) {
                        setOrgRepoSelected(new Set());
                      } else {
                        setOrgRepoSelected(new Set(notAdded));
                      }
                    }}
                    style={{ padding: '4px 12px', background: '#6c757d', color: '#fff', border: 'none', borderRadius: '4px', fontSize: '12px', cursor: 'pointer' }}
                  >
                    {orgRepoSelected.size > 0 ? 'Deselect All' : 'Select All'}
                  </button>
                  <button
                    onClick={async () => {
                      if (orgRepoSelected.size === 0) return;
                      setAddingSelected(true);
                      let added = 0;
                      for (const fullName of orgRepoSelected) {
                        const repo = orgRepos.find(r => r.full_name === fullName);
                        if (!repo || repo.already_added) continue;
                        try {
                          await fetchApi('/api/github/repos', {
                            method: 'POST',
                            body: JSON.stringify({
                              owner: repo.owner,
                              repo_name: repo.repo_name,
                              description: repo.description,
                              default_branch: repo.default_branch,
                            }),
                          });
                          added++;
                          repo.already_added = true;
                        } catch { /* duplicate or error — skip */ }
                      }
                      setOrgRepoSelected(new Set());
                      setRepoMsg(`Added ${added} repositories for QA.`);
                      setAddingSelected(false);
                      // Refresh repo list
                      fetchApi<{ items: typeof repos }>('/api/github/repos')
                        .then(data => setRepos(data.items))
                        .catch(() => {});
                    }}
                    disabled={orgRepoSelected.size === 0 || addingSelected}
                    style={{
                      padding: '4px 12px',
                      background: orgRepoSelected.size > 0 && !addingSelected ? '#28a745' : '#ccc',
                      color: '#fff', border: 'none', borderRadius: '4px', fontSize: '12px',
                      cursor: orgRepoSelected.size > 0 && !addingSelected ? 'pointer' : 'default',
                      fontWeight: 600,
                    }}
                  >
                    {addingSelected ? 'Adding...' : `Add ${orgRepoSelected.size} Selected`}
                  </button>
                </div>
              </div>
              <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid #dee2e6', borderRadius: '4px', background: '#fff' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #dee2e6', textAlign: 'left', position: 'sticky', top: 0, background: '#f8f9fa' }}>
                      <th style={{ padding: '8px', width: '35px' }}></th>
                      <th style={{ padding: '8px' }}>Repository</th>
                      <th style={{ padding: '8px' }}>Description</th>
                      <th style={{ padding: '8px', width: '80px' }}>Language</th>
                      <th style={{ padding: '8px', width: '60px' }}>Stars</th>
                      <th style={{ padding: '8px', width: '90px' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orgRepos.map(repo => {
                      const isSelected = orgRepoSelected.has(repo.full_name);
                      return (
                        <tr
                          key={repo.full_name}
                          style={{
                            borderBottom: '1px solid #f0f0f0',
                            background: repo.already_added ? '#f8f8f8' : isSelected ? '#e8f4fd' : 'transparent',
                            cursor: repo.already_added ? 'default' : 'pointer',
                            opacity: repo.already_added ? 0.7 : 1,
                          }}
                          onClick={() => {
                            if (repo.already_added) return;
                            setOrgRepoSelected(prev => {
                              const next = new Set(prev);
                              if (next.has(repo.full_name)) next.delete(repo.full_name);
                              else next.add(repo.full_name);
                              return next;
                            });
                          }}
                        >
                          <td style={{ padding: '8px' }}>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              disabled={repo.already_added}
                              onChange={() => {}}
                              style={{ cursor: repo.already_added ? 'default' : 'pointer' }}
                            />
                          </td>
                          <td style={{ padding: '8px' }}>
                            <a href={repo.html_url} target="_blank" rel="noopener noreferrer"
                              onClick={e => e.stopPropagation()}
                              style={{ color: '#0f3460', fontWeight: 600, textDecoration: 'none' }}>
                              {repo.full_name}
                            </a>
                            {repo.private && <span style={{ marginLeft: '6px', background: '#ffc107', color: '#333', padding: '1px 5px', borderRadius: '3px', fontSize: '10px', fontWeight: 600 }}>PRIVATE</span>}
                          </td>
                          <td style={{ padding: '8px', color: '#666', fontSize: '12px' }}>
                            {repo.description ? (repo.description.length > 60 ? repo.description.slice(0, 60) + '...' : repo.description) : '—'}
                          </td>
                          <td style={{ padding: '8px', fontSize: '12px' }}>{repo.language || '—'}</td>
                          <td style={{ padding: '8px', fontSize: '12px' }}>{repo.stars}</td>
                          <td style={{ padding: '8px' }}>
                            {repo.already_added ? (
                              <span style={{ color: '#28a745', fontSize: '11px', fontWeight: 600 }}>ADDED ✓</span>
                            ) : (
                              <span style={{ color: '#6c757d', fontSize: '11px' }}>Available</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {repoMsg && <p style={msgStyle(repoMsg)}>{repoMsg}</p>}

        {/* Repository List */}
        {repos.length > 0 ? (
          <div>
            {repos.map(repo => (
              <div
                key={repo.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '12px 0',
                  borderBottom: '1px solid #f0f0f0',
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '14px', color: '#0f3460' }}>
                    {repo.owner}/{repo.repo_name}
                    {!repo.active && (
                      <span style={{
                        marginLeft: '8px',
                        fontSize: '11px',
                        color: '#dc3545',
                        fontWeight: 500,
                      }}>
                        (inactive)
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '12px', color: '#666', marginTop: '2px' }}>
                    {repo.description && <span>{repo.description} &middot; </span>}
                    branch: <strong>{repo.default_branch}</strong>
                    {' '}&middot; auto-fetch: <strong>{repo.auto_fetch ? 'yes' : 'no'}</strong>
                    {repo.qa_tiers && (
                      <span> &middot; tiers: <strong>{repo.qa_tiers}</strong></span>
                    )}
                  </div>
                </div>
                <button style={dangerButtonStyle} onClick={() => deleteRepo(repo.id)}>
                  Delete
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: '#999', fontSize: '14px' }}>No repositories configured.</p>
        )}
      </div>

      {/* ===== Section 5: Feature Toggles ===== */}
      <div style={cardStyle}>
        <h3 style={headingStyle}>Feature Toggles</h3>
        {settings?.features ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 24px' }}>
            {Object.entries(settings.features).map(([key, enabled]) => (
              <div
                key={key}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '10px 0',
                  borderBottom: '1px solid #f0f0f0',
                }}
              >
                <span style={{ textTransform: 'capitalize', fontWeight: 500, fontSize: '14px' }}>
                  {key}
                </span>
                <span
                  style={{
                    color: enabled ? '#28a745' : '#dc3545',
                    fontWeight: 600,
                    fontSize: '12px',
                  }}
                >
                  {enabled ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: '#999', fontSize: '14px' }}>No feature toggle data available.</p>
        )}
      </div>

      {/* ===== Section 6: Automation Rules ===== */}
      <div style={cardStyle}>
        <h3 style={headingStyle}>Automation Rules</h3>
        {rules.length > 0 ? (
          rules.map(rule => (
            <div
              key={rule.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '10px 0',
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              <div>
                <div style={{ fontWeight: 500, fontSize: '14px' }}>{rule.name}</div>
                <div style={{ fontSize: '12px', color: '#666' }}>{rule.trigger}</div>
              </div>
              <button
                onClick={() => toggleRule(rule)}
                style={{
                  padding: '4px 14px',
                  border: '1px solid',
                  borderColor: rule.active ? '#28a745' : '#dc3545',
                  borderRadius: '4px',
                  background: 'transparent',
                  color: rule.active ? '#28a745' : '#dc3545',
                  fontWeight: 600,
                  fontSize: '11px',
                  cursor: 'pointer',
                }}
              >
                {rule.active ? 'ACTIVE' : 'INACTIVE'}
              </button>
            </div>
          ))
        ) : (
          <p style={{ color: '#999', fontSize: '14px' }}>No automation rules configured.</p>
        )}
      </div>
    </div>
  );
}
