import { useMemo } from 'react';
import { Product } from '../types/models';
import { useApp } from '../context/AppContext';
import { toDisplay } from '../utils/unitConversion';

interface DistributionChartProps {
  products: Product[];
  attribute: string;
  title: string;
}

export default function DistributionChart({ products, attribute, title }: DistributionChartProps) {
  const { unitSystem } = useApp();

  const resolve = (product: any, path: string): any => {
    if (!product) return null;
    if (path.includes('.')) {
      const parts = path.split('.');
      let current = product;
      for (const part of parts) {
        if (current === null || current === undefined) return null;
        current = current[part];
      }
      return current;
    }
    return product[path];
  };

  // Bucket by canonical value (so toggling units doesn't reshuffle the
  // chart), but render labels through toDisplay() so imperial readers
  // see imperial numbers. Unit string is sniffed from the first value
  // that carries one — for ValueUnit/MinMaxUnit fields they all match.
  const formatLabel = (val: any, unit: string | null): string => {
    if (val === null || val === undefined) return 'Unknown';
    if (typeof val === 'object') {
      if ('value' in val) {
        const u = val.unit ?? unit ?? '';
        return typeof val.value === 'number' && u
          ? String(toDisplay(val.value, u, unitSystem))
          : String(val.value);
      }
      if ('min' in val && 'max' in val) {
        const u = val.unit ?? unit ?? '';
        if (u && typeof val.min === 'number' && typeof val.max === 'number') {
          return `${toDisplay(val.min, u, unitSystem)}-${toDisplay(val.max, u, unitSystem)}`;
        }
        return `${val.min}-${val.max}`;
      }
      return JSON.stringify(val);
    }
    return String(val);
  };

  const distribution = useMemo(() => {
    const counts: Record<string, number> = {};
    let total = 0;

    // First pass: sniff the canonical unit for this attribute so the
    // label formatter can convert consistently regardless of which
    // record happens to be first.
    let attrUnit: string | null = null;
    for (const product of products) {
      const raw = resolve(product, attribute);
      if (
        raw !== null
        && typeof raw === 'object'
        && raw !== null
        && 'unit' in raw
        && typeof raw.unit === 'string'
      ) {
        attrUnit = raw.unit;
        break;
      }
    }

    products.forEach(product => {
      const raw = resolve(product, attribute);
      const label = formatLabel(raw, attrUnit);
      counts[label] = (counts[label] || 0) + 1;
      total++;
    });

    const sortedAll = Object.entries(counts)
      .sort(([, a], [, b]) => b - a);

    // Top 3 only — keep it tight
    const top = sortedAll.slice(0, 3);
    const otherCount = sortedAll.slice(3).reduce((sum, [, count]) => sum + count, 0);

    const result = top.map(([name, count]) => ({
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
  }, [products, attribute, unitSystem]);

  const colors = ['#3b82f6', '#10b981', '#f59e0b'];

  const getColor = (index: number, name: string) => {
    if (name === 'Other') return 'var(--text-tertiary)';
    return colors[index] || colors[0];
  };

  if (distribution.total === 0) return null;

  return (
    <div style={{ marginTop: '0.75rem', paddingTop: '0.6rem', borderTop: '1px solid var(--border-color)' }}>
      <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.03em', marginBottom: '0.4rem' }}>
        {title}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        {distribution.items.map((item, index) => {
          const isOther = item.name === 'Other';
          return (
            <div key={item.name} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {/* Horizontal bar */}
              <div style={{
                flex: 1,
                height: '6px',
                backgroundColor: 'var(--bg-tertiary)',
                borderRadius: '3px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${item.percentage}%`,
                  height: '100%',
                  backgroundColor: getColor(index, item.name),
                  borderRadius: '3px',
                  opacity: isOther ? 0.5 : 0.8,
                  transition: 'width 0.3s ease'
                }} />
              </div>
              {/* Percentage — bold and prominent */}
              <span style={{
                fontSize: isOther ? '0.65rem' : '0.75rem',
                fontWeight: isOther ? 400 : 700,
                color: isOther ? 'var(--text-tertiary)' : 'var(--text-primary)',
                minWidth: '30px',
                textAlign: 'right',
                fontVariantNumeric: 'tabular-nums'
              }}>
                {Math.round(item.percentage)}%
              </span>
            </div>
          );
        })}
      </div>

      {/* Labels under bars — compact row */}
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.2rem', flexWrap: 'wrap' }}>
        {distribution.items.filter(i => i.name !== 'Other').map((item, index) => (
          <span key={item.name} style={{
            fontSize: '0.6rem',
            color: 'var(--text-secondary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: '70px',
            display: 'flex',
            alignItems: 'center',
            gap: '0.2rem'
          }} title={`${item.name}: ${item.count}`}>
            <span style={{
              width: '5px',
              height: '5px',
              borderRadius: '50%',
              backgroundColor: getColor(index, item.name),
              flexShrink: 0
            }} />
            {item.name}
          </span>
        ))}
      </div>
    </div>
  );
}
