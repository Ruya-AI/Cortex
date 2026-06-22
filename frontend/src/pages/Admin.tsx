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
  configured: boolean;
}

interface LinearSettings {
  api_key: string;
  team_id: string;
  workspace_name: string;
  auto_create_tasks: boolean;
  min_severity: string;
  max_tasks_per_scan: number;
  configured: boolean;
}

interface NotificationSettings {
  slack_webhook_url: string;
  email: string;
  notify_on_critical: boolean;
  notify_on_gate_failure: boolean;
  configured: boolean;
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
  const [repoOwner, setRepoOwner] = useState('');
  const [repoName, setRepoName] = useState('');
  const [repoDesc, setRepoDesc] = useState('');
  const [repoBranch, setRepoBranch] = useState('main');
  const [repoAutoFetch, setRepoAutoFetch] = useState(true);
  const [repoQaTiers, setRepoQaTiers] = useState('t1,t2');
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
    fetchApi<GitHubSettings>('/api/admin/github')
      .then(data => {
        if (data) {
          setGhApiUrl(data.api_url || 'https://api.github.com');
          setGhConfigured(data.configured ?? false);
          // Token is never returned in full for security
        }
      })
      .catch(() => {});

    // Linear settings
    fetchApi<LinearSettings>('/api/admin/linear')
      .then(data => {
        if (data) {
          setLinearTeamId(data.team_id || '');
          setLinearWorkspace(data.workspace_name || '');
          setLinearAutoCreate(data.auto_create_tasks ?? false);
          setLinearMinSeverity(data.min_severity || 'high');
          setLinearMaxTasks(data.max_tasks_per_scan ?? 10);
          setLinearConfigured(data.configured ?? false);
        }
      })
      .catch(() => {});

    // Notification settings
    fetchApi<NotificationSettings>('/api/admin/notifications')
      .then(data => {
        if (data) {
          setSlackWebhook(data.slack_webhook_url || '');
          setNotifEmail(data.email || '');
          setNotifCritical(data.notify_on_critical ?? true);
          setNotifGateFailure(data.notify_on_gate_failure ?? true);
          setNotifConfigured(data.configured ?? false);
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
    if (!ghToken) return;
    setGhMsg('');
    fetchApi('/api/admin/github', {
      method: 'PUT',
      body: JSON.stringify({ token: ghToken, api_url: ghApiUrl }),
    })
      .then(() => {
        setGhMsg('GitHub settings saved.');
        setGhConfigured(true);
        setGhToken('');
      })
      .catch(() => setGhMsg('Failed to save GitHub settings.'));
  };

  const saveLinear = () => {
    if (!linearApiKey) return;
    setLinearMsg('');
    fetchApi('/api/admin/linear', {
      method: 'PUT',
      body: JSON.stringify({
        api_key: linearApiKey,
        team_id: linearTeamId,
        workspace_name: linearWorkspace,
        auto_create_tasks: linearAutoCreate,
        min_severity: linearMinSeverity,
        max_tasks_per_scan: linearMaxTasks,
      }),
    })
      .then(() => {
        setLinearMsg('Linear settings saved.');
        setLinearConfigured(true);
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
        notify_on_critical: notifCritical,
        notify_on_gate_failure: notifGateFailure,
      }),
    })
      .then(() => {
        setNotifMsg('Notification settings saved.');
        setNotifConfigured(true);
      })
      .catch(() => setNotifMsg('Failed to save notification settings.'));
  };

  const addRepo = () => {
    if (!repoOwner || !repoName) return;
    setRepoMsg('');
    fetchApi('/api/github/repos', {
      method: 'POST',
      body: JSON.stringify({
        owner: repoOwner,
        repo_name: repoName,
        description: repoDesc,
        default_branch: repoBranch,
        auto_fetch: repoAutoFetch,
        qa_tiers: repoQaTiers,
      }),
    })
      .then(() => {
        setRepoMsg('Repository added.');
        setRepoOwner('');
        setRepoName('');
        setRepoDesc('');
        setRepoBranch('main');
        setRepoAutoFetch(true);
        setRepoQaTiers('t1,t2');
        // Refresh repo list
        fetchApi<{ items: Repository[] }>('/api/github/repos')
          .then(data => setRepos(data.items || []))
          .catch(() => {});
      })
      .catch(() => setRepoMsg('Failed to add repository.'));
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

        {/* Add Repository Form */}
        <div style={{
          background: '#f8f9fa',
          borderRadius: '6px',
          padding: '16px',
          marginBottom: '20px',
          border: '1px solid #e9ecef',
        }}>
          <h4 style={{ margin: '0 0 14px 0', fontSize: '14px', color: '#495057' }}>Add Repository</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Owner</label>
              <input
                style={inputStyle}
                value={repoOwner}
                onChange={e => setRepoOwner(e.target.value)}
                placeholder="e.g. Ruya-AI"
              />
            </div>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Repository Name</label>
              <input
                style={inputStyle}
                value={repoName}
                onChange={e => setRepoName(e.target.value)}
                placeholder="e.g. Cortex"
              />
            </div>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Default Branch</label>
              <input
                style={inputStyle}
                value={repoBranch}
                onChange={e => setRepoBranch(e.target.value)}
                placeholder="main"
              />
            </div>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Description</label>
              <input
                style={inputStyle}
                value={repoDesc}
                onChange={e => setRepoDesc(e.target.value)}
                placeholder="Brief description"
              />
            </div>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>QA Tiers</label>
              <input
                style={inputStyle}
                value={repoQaTiers}
                onChange={e => setRepoQaTiers(e.target.value)}
                placeholder="t1,t2,t3"
              />
            </div>
            <div style={{ ...fieldGroupStyle, display: 'flex', alignItems: 'flex-end', gap: '8px', paddingBottom: '2px' }}>
              <input
                type="checkbox"
                checked={repoAutoFetch}
                onChange={e => setRepoAutoFetch(e.target.checked)}
                id="repo-auto-fetch"
              />
              <label htmlFor="repo-auto-fetch" style={{ fontSize: '13px', fontWeight: 500, color: '#333' }}>
                Auto-fetch PRs
              </label>
            </div>
          </div>
          <button style={{ ...buttonStyle, background: '#28a745' }} onClick={addRepo}>Add Repository</button>
          {repoMsg && <p style={msgStyle(repoMsg)}>{repoMsg}</p>}
        </div>

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
