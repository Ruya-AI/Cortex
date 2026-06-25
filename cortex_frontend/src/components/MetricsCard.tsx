interface MetricsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: string;
}

export function MetricsCard({ title, value, subtitle, color = '#0f3460' }: MetricsCardProps) {
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #dee2e6',
      borderRadius: '8px',
      padding: '20px',
      minWidth: '160px',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: '28px', fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: '12px', color: '#6c757d', textTransform: 'uppercase', marginTop: '4px' }}>{title}</div>
      {subtitle && <div style={{ fontSize: '11px', color: '#999', marginTop: '2px' }}>{subtitle}</div>}
    </div>
  );
}
