import { useMemo } from 'react';
import { Product } from '../types/models';

interface ManufacturerPieChartProps {
  products: Product[];
}

export default function ManufacturerPieChart({ products }: ManufacturerPieChartProps) {
  // Calculate distribution
  const distribution = useMemo(() => {
    const counts: Record<string, number> = {};
    let total = 0;

    products.forEach(product => {
      const manufacturer = product.manufacturer || 'Unknown';
      counts[manufacturer] = (counts[manufacturer] || 0) + 1;
      total++;
    });

    // Sort by count descending
    const sorted = Object.entries(counts)
      .sort(([, a], [, b]) => b - a)
      .map(([name, count]) => ({
        name,
        count,
        percentage: (count / total) * 100
      }));

    return { sorted, total };
  }, [products]);

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

  const getColor = (index: number) => colors[index % colors.length];

  if (distribution.total === 0) return null;

  // Create conic-gradient string
  let currentAngle = 0;
  const gradientParts = distribution.sorted.map((item, index) => {
    const start = currentAngle;
    const angle = (item.count / distribution.total) * 360;
    currentAngle += angle;
    return `${getColor(index)} ${start}deg ${currentAngle}deg`;
  });

  const gradient = `conic-gradient(${gradientParts.join(', ')})`;

  return (
    <div className="manufacturer-distribution" style={{ marginTop: '2rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
      <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--text-primary)' }}>
        Manufacturer Distribution
      </h3>
      
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.5rem' }}>
        {/* Pie Chart */}
        <div 
          style={{
            width: '120px',
            height: '120px',
            borderRadius: '50%',
            background: gradient,
            position: 'relative',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
          }}
        />

        {/* Legend */}
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {distribution.sorted.map((item, index) => (
            <div key={item.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ 
                  width: '8px', 
                  height: '8px', 
                  borderRadius: '50%', 
                  backgroundColor: getColor(index),
                  display: 'inline-block'
                }} />
                <span style={{ color: 'var(--text-secondary)' }}>{item.name}</span>
              </div>
              <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                {Math.round(item.percentage)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
