import { useMemo } from 'react';
import { Product } from '../types/models';

interface DistributionChartProps {
  products: Product[];
  attribute: string;
  title: string;
}

export default function DistributionChart({ products, attribute, title }: DistributionChartProps) {
  // Helper to extract value from product (handles nested properties)
  const getValue = (product: any, path: string): string => {
    if (!product) return 'Unknown';
    
    // Handle dot notation for nested properties
    if (path.includes('.')) {
      const parts = path.split('.');
      let current = product;
      for (const part of parts) {
        if (current === null || current === undefined) return 'Unknown';
        current = current[part];
      }
      return formatValue(current);
    }

    return formatValue(product[path]);
  };

  const formatValue = (val: any): string => {
    if (val === null || val === undefined) return 'Unknown';
    if (typeof val === 'object') {
      if ('value' in val) return String(val.value);
      if ('min' in val && 'max' in val) return `${val.min}-${val.max}`;
      return JSON.stringify(val);
    }
    return String(val);
  };

  // Calculate distribution
  const distribution = useMemo(() => {
    const counts: Record<string, number> = {};
    let total = 0;

    products.forEach(product => {
      const value = getValue(product, attribute);
      counts[value] = (counts[value] || 0) + 1;
      total++;
    });

    // Sort by count descending and take top 5 + Other
    const sortedAll = Object.entries(counts)
      .sort(([, a], [, b]) => b - a);
    
    let finalItems = sortedAll;
    let otherCount = 0;

    // If too many items, group into "Other"
    if (sortedAll.length > 6) {
      finalItems = sortedAll.slice(0, 5);
      otherCount = sortedAll.slice(5).reduce((sum, [, count]) => sum + count, 0);
    }

    const result = finalItems.map(([name, count]) => ({
      name,
      count,
      percentage: (count / total) * 100
    }));

    if (otherCount > 0) {
      result.push({
        name: 'Other',
        count: otherCount,
        percentage: (otherCount / total) * 100
      });
    }

    return { items: result, total };
  }, [products, attribute]);

  // Generate colors (simple palette)
  const colors = [
    '#3b82f6', // blue
    '#ef4444', // red
    '#10b981', // green
    '#f59e0b', // yellow
    '#8b5cf6', // purple
    '#ec4899', // pink
    '#06b6d4', // cyan
    '#6366f1', // indigo
    '#84cc16', // lime
    '#f97316', // orange
  ];

  const getColor = (index: number, name: string) => {
    if (name === 'Other') return '#9ca3af'; // Gray for Other
    return colors[index % colors.length];
  };

  if (distribution.total === 0) return null;

  return (
    <div className="distribution-chart" style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
      <h3 style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
        {title} Distribution
      </h3>
      
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
        {/* Stacked Vertical Bar Chart */}
        <div 
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: '120px',
            width: '24px',
            backgroundColor: 'var(--bg-secondary)',
            borderRadius: '4px',
            overflow: 'hidden',
            border: '1px solid var(--border-color)'
          }}
        >
          {distribution.items.map((item, index) => (
            <div
              key={item.name}
              style={{
                width: '100%',
                height: `${item.percentage}%`,
                backgroundColor: getColor(index, item.name),
                transition: 'height 0.3s ease',
                position: 'relative'
              }}
              title={`${item.name}: ${item.count} (${Math.round(item.percentage)}%)`}
            />
          ))}
        </div>

        {/* Legend on the Right */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.3rem', overflow: 'hidden' }}>
          {distribution.items.map((item, index) => (
            <div key={item.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.7rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', overflow: 'hidden' }}>
                <span style={{ 
                  width: '6px', 
                  height: '6px', 
                  borderRadius: '50%', 
                  backgroundColor: getColor(index, item.name),
                  display: 'inline-block',
                  flexShrink: 0
                }} />
                <span style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={item.name}>
                  {item.name}
                </span>
              </div>
              <span style={{ fontWeight: 500, color: 'var(--text-primary)', marginLeft: '4px' }}>
                {Math.round(item.percentage)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
