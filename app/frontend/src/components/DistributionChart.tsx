import { useMemo } from 'react';
import { Product } from '../types/models';
import { AttributeMetadata } from '../types/filters';
import { useApp } from '../context/AppContext';
import { toDisplay, displayUnit } from '../utils/unitConversion';

interface DistributionChartProps {
  products: Product[];
  attribute: string;
  title: string;
  attributeType?: AttributeMetadata['type'];
}

// Numeric attributes with more than this many distinct values are too
// scattered for a top-3 categorical breakdown — every bar would be its
// own value and "Other" would dominate. Switch to a binned histogram
// once cardinality crosses this floor.
const HISTOGRAM_MIN_DISTINCT = 6;
const HISTOGRAM_BINS = 10;

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

// Pull a comparable scalar out of ValueUnit, MinMaxUnit, or a bare
// number. MinMaxUnit collapses to its midpoint so a single record
// contributes one point, matching the slider's extractNumericValue.
const extractNumeric = (val: any): number | null => {
  if (typeof val === 'number') return val;
  if (val && typeof val === 'object') {
    if ('value' in val && typeof val.value === 'number') return val.value;
    if ('min' in val && 'max' in val && typeof val.min === 'number' && typeof val.max === 'number') {
      return (val.min + val.max) / 2;
    }
  }
  return null;
};

const sniffUnit = (val: any): string | null => {
  if (val && typeof val === 'object' && 'unit' in val && typeof val.unit === 'string') {
    return val.unit;
  }
  return null;
};

// Format a histogram tick. Small magnitudes get one decimal so 0.5 / 1.0
// don't both render as "1"; everything else rounds to an integer for a
// tighter axis line.
const formatTick = (n: number): string => {
  if (!Number.isFinite(n)) return '–';
  if (Math.abs(n) < 10) return n.toFixed(1).replace(/\.0$/, '');
  return Math.round(n).toLocaleString();
};

export default function DistributionChart({ products, attribute, title, attributeType }: DistributionChartProps) {
  const { unitSystem } = useApp();

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

  // Single-pass scan — collects both the categorical buckets and the
  // numeric points, then we decide downstream which view to render.
  const summary = useMemo(() => {
    const counts: Record<string, number> = {};
    const numeric: number[] = [];
    let attrUnit: string | null = null;
    let total = 0;

    for (const product of products) {
      const raw = resolve(product, attribute);
      if (raw === null || raw === undefined) continue;
      if (attrUnit === null) {
        const u = sniffUnit(raw);
        if (u) attrUnit = u;
      }
      const label = formatLabel(raw, attrUnit);
      counts[label] = (counts[label] || 0) + 1;
      const num = extractNumeric(raw);
      if (num !== null && Number.isFinite(num)) numeric.push(num);
      total++;
    }

    return { counts, numeric, attrUnit, total };
  }, [products, attribute, unitSystem]);

  // Histogram trigger: explicitly numeric attribute kinds with enough
  // distinct values that a top-3 list would just say "everything is
  // Other". `number` type alone isn't enough — discrete fields like
  // poles or ip_rating want the categorical view.
  const useHistogram = useMemo(() => {
    const isNumericKind =
      attributeType === 'object' || attributeType === 'range' || attributeType === 'number';
    if (!isNumericKind) return false;
    if (summary.numeric.length < HISTOGRAM_MIN_DISTINCT) return false;
    const distinct = new Set(summary.numeric).size;
    return distinct >= HISTOGRAM_MIN_DISTINCT;
  }, [attributeType, summary.numeric]);

  // --- Histogram path ---------------------------------------------------
  // Percentile-spaced bins — same approach as the slider's
  // valueToPosition (FilterChip.tsx). Each bin spans an equal slice of
  // the empirical CDF, and the bar height is *density* (count divided
  // by the bin's value-span). With linear-value bins, a single 10×
  // outlier compressed the bulk of the distribution into bin 0 and
  // forced bins 1–8 to zero. Equal-frequency bins flip that: the
  // outlier's bin is wide on the value axis but short on the density
  // axis, while the dense median sits in narrow bins that render as
  // tall bars. Distribution shape survives an outlier, mirroring how
  // the slider track gives an outlier a slice proportional to its
  // rarity.
  const histogram = useMemo(() => {
    if (!useHistogram || summary.numeric.length === 0) return null;
    const values = [...summary.numeric].sort((a, b) => a - b);
    const n = values.length;
    if (n === 0) return null;
    const min = values[0];
    const max = values[n - 1];
    if (min === max) {
      return {
        bins: [{ count: n, lo: min, hi: max, density: 1 }],
        min,
        max,
        peak: 1,
      };
    }
    // Cap bin count at n so a small dataset doesn't render alternating
    // empty slots (n=6 vs. 10 fixed bins → every other bin empty).
    const numBins = Math.min(HISTOGRAM_BINS, n);
    const bins: Array<{ count: number; lo: number; hi: number; density: number }> = [];
    for (let i = 0; i < numBins; i++) {
      const loIdx = Math.floor((i * n) / numBins);
      const hiIdx =
        i === numBins - 1
          ? n
          : Math.floor(((i + 1) * n) / numBins);
      const count = hiIdx - loIdx;
      if (count === 0) {
        bins.push({ count: 0, lo: 0, hi: 0, density: 0 });
        continue;
      }
      const lo = values[loIdx];
      const hi = i === numBins - 1 ? values[n - 1] : values[hiIdx];
      const span = hi - lo;
      // Spike bins (multiple tied records) have span 0; resolve below
      // to the chart's finite density peak so a tie reads as "tall"
      // rather than zeroing out or blowing the y-scale.
      const density = span > 0 ? count / span : Number.POSITIVE_INFINITY;
      bins.push({ count, lo, hi, density });
    }
    let finitePeak = 0;
    for (const b of bins) {
      if (Number.isFinite(b.density) && b.density > finitePeak) finitePeak = b.density;
    }
    if (finitePeak === 0) finitePeak = 1;
    for (const b of bins) {
      if (!Number.isFinite(b.density)) b.density = finitePeak;
    }
    return { bins, min, max, peak: finitePeak };
  }, [useHistogram, summary.numeric]);

  // --- Categorical path (existing) -------------------------------------
  const distribution = useMemo(() => {
    if (useHistogram) return { items: [], total: summary.total };
    const sortedAll = Object.entries(summary.counts).sort(([, a], [, b]) => b - a);
    const top = sortedAll.slice(0, 3);
    const otherCount = sortedAll.slice(3).reduce((sum, [, count]) => sum + count, 0);
    const result = top.map(([name, count]) => ({
      name,
      count,
      percentage: summary.total === 0 ? 0 : (count / summary.total) * 100,
    }));
    if (otherCount > 0) {
      result.push({
        name: 'Other',
        count: otherCount,
        percentage: summary.total === 0 ? 0 : (otherCount / summary.total) * 100,
      });
    }
    return { items: result, total: summary.total };
  }, [useHistogram, summary]);

  // Monochromatic ink with a stroke escape for rank 3: top two ranks are
  // filled accent at stepped opacity, third rank is transparent with a
  // 1px accent outline. The shape change (filled vs. outlined) reads
  // faster than another opacity step would, and keeps "Other" — which
  // is filled in tertiary gray — visually distinct from rank 3.
  const rankOpacity = [1, 0.6];
  const isOutlineRank = (index: number, name: string) =>
    name !== 'Other' && index >= 2;
  const getColor = (_index: number, name: string) =>
    name === 'Other' ? 'var(--text-tertiary)' : 'var(--accent-primary)';
  const getOpacity = (index: number, name: string) => {
    if (name === 'Other') return 0.4;
    if (isOutlineRank(index, name)) return 1;
    return rankOpacity[index] ?? rankOpacity[rankOpacity.length - 1];
  };

  if (summary.total === 0) return null;

  const heading = (
    <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.03em', marginBottom: '0.25rem' }}>
      {title}
    </div>
  );

  if (useHistogram && histogram) {
    const unit = summary.attrUnit ?? '';
    const dispMin = unit ? toDisplay(histogram.min, unit, unitSystem) : histogram.min;
    const dispMax = unit ? toDisplay(histogram.max, unit, unitSystem) : histogram.max;
    const dispUnit = unit ? displayUnit(unit, unitSystem) : '';
    return (
      <div style={{ marginTop: '0.5rem', paddingTop: '0.4rem', borderTop: '1px solid var(--border-color)' }}>
        {heading}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: '2px',
            height: '26px',
            padding: '0 1px',
          }}
          title={`${summary.numeric.length} value${summary.numeric.length === 1 ? '' : 's'} across ${HISTOGRAM_BINS} bins`}
        >
          {histogram.bins.map((bin, i) => {
            const pct = histogram.peak === 0 ? 0 : (bin.density / histogram.peak) * 100;
            const lo = unit ? toDisplay(bin.lo, unit, unitSystem) : bin.lo;
            const hi = unit ? toDisplay(bin.hi, unit, unitSystem) : bin.hi;
            return (
              <div
                key={i}
                style={{
                  flex: 1,
                  height: '100%',
                  display: 'flex',
                  alignItems: 'flex-end',
                }}
                title={`${formatTick(lo)} – ${formatTick(hi)}${dispUnit ? ' ' + dispUnit : ''} · ${bin.count} record${bin.count === 1 ? '' : 's'}`}
              >
                <div
                  style={{
                    width: '100%',
                    // Floor every non-empty bin at a 2px sliver so users
                    // can still click/hover bins with a single record —
                    // a pure proportional bar would render invisibly.
                    height: bin.count === 0 ? '0%' : `max(2px, ${pct}%)`,
                    backgroundColor: 'var(--accent-primary)',
                    opacity: bin.count === 0 ? 0 : 0.35 + 0.65 * (pct / 100),
                    borderRadius: '1px',
                    transition: 'height 0.2s ease, opacity 0.2s ease',
                  }}
                />
              </div>
            );
          })}
        </div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: '0.15rem',
            fontSize: '0.7rem',
            color: 'var(--text-tertiary)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          <span>{formatTick(dispMin)}{dispUnit ? ` ${dispUnit}` : ''}</span>
          <span>{formatTick(dispMax)}{dispUnit ? ` ${dispUnit}` : ''}</span>
        </div>
      </div>
    );
  }

  return (
    <div style={{ marginTop: '0.5rem', paddingTop: '0.4rem', borderTop: '1px solid var(--border-color)' }}>
      {heading}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
        {distribution.items.map((item, index) => {
          const isOther = item.name === 'Other';
          const outlined = isOutlineRank(index, item.name);
          const color = getColor(index, item.name);
          return (
            <div key={item.name} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {/* Horizontal bar */}
              <div style={{
                flex: 1,
                height: '5px',
                backgroundColor: 'var(--bg-tertiary)',
                borderRadius: '3px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${item.percentage}%`,
                  height: '100%',
                  backgroundColor: outlined ? 'transparent' : color,
                  boxShadow: outlined ? `inset 0 0 0 1px ${color}` : undefined,
                  borderRadius: '3px',
                  opacity: getOpacity(index, item.name),
                  transition: 'width 0.3s ease'
                }} />
              </div>
              {/* Percentage — bold and prominent */}
              <span style={{
                fontSize: '0.75rem',
                fontWeight: isOther ? 400 : 700,
                color: isOther ? 'var(--text-tertiary)' : 'var(--text-primary)',
                minWidth: '28px',
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
      <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.15rem', flexWrap: 'wrap' }}>
        {distribution.items.filter(i => i.name !== 'Other').map((item, index) => {
          const outlined = isOutlineRank(index, item.name);
          const color = getColor(index, item.name);
          return (
            <span key={item.name} style={{
              fontSize: '0.72rem',
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
                backgroundColor: outlined ? 'transparent' : color,
                boxShadow: outlined ? `inset 0 0 0 1px ${color}` : undefined,
                opacity: getOpacity(index, item.name),
                flexShrink: 0
              }} />
              {item.name}
            </span>
          );
        })}
      </div>
    </div>
  );
}
