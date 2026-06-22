const COLORS: Record<string, { bg: string; text: string }> = {
  critical: { bg: '#dc3545', text: '#fff' },
  high: { bg: '#fd7e14', text: '#fff' },
  medium: { bg: '#ffc107', text: '#333' },
  low: { bg: '#28a745', text: '#fff' },
  info: { bg: '#6c757d', text: '#fff' },
};

export function SeverityBadge({ severity }: { severity: string }) {
  const color = COLORS[severity] || COLORS.info;
  return (
    <span style={{
      backgroundColor: color.bg,
      color: color.text,
      padding: '2px 8px',
      borderRadius: '4px',
      fontSize: '12px',
      fontWeight: 600,
    }}>
      {severity.toUpperCase()}
    </span>
  );
}
