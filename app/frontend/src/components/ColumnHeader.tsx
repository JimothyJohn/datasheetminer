/**
 * Column header that combines the histogram, sortable label, and inline
 * slider for one product attribute. Replaces the separate filter pane:
 * every filter lives in the column it filters.
 *
 * Layout (fixed-height rows so the grid lines up across columns):
 *
 *   ┌───────────────────────────┐
 *   │ ▁▂▅▇▅▂▁ histogram         │  HIST_H
 *   │ RATED TORQUE  ↑           │  LABEL_H — click to sort
 *   │ ━━━━●━━━━━━━━━━━━         │  SLIDER_H
 *   │ ≥  0.3  Nm                │  READOUT_H — operator/value/unit each clickable
 *   └───────────────────────────┘
 *
 * Histogram and slider scale are anchored to `allProducts` (the
 * unfiltered, linearized source) so the visual reference stays put as
 * the user dials in filters. Bar heights still come from the filtered
 * `products` so the user can see the slice they've selected.
 *
 * Pristine state: when no filter exists for this column, the slider is
 * parked at 0% with operator '>=' and the readout reads 'any'. The first
 * pointer-down on the track promotes it into a real filter.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AttributeMetadata,
  ComparisonOperator,
  FilterCriterion,
  SortConfig,
} from '../types/filters';
import { Product } from '../types/models';
import {
  UnitSystem,
  displayUnit,
  isIntegerUnit,
  toCanonical,
  toDisplay,
} from '../utils/unitConversion';
import DistributionChart from './DistributionChart';

interface ColumnHeaderProps {
  attribute: AttributeMetadata;
  label: string;
  /** Filtered, post-linearization rows. Drives the histogram bar heights. */
  products: Product[];
  /** Unfiltered linearized source. Anchors the slider scale and the
   *  histogram x-range so the visual reference doesn't jump. */
  allProducts: Product[];
  filter: FilterCriterion | null;
  sortConfig: SortConfig | null;
  sortIndex: number;
  totalSorts: number;
  width: number;
  /** Effective unit system for this column. Per-column, not global —
   *  flipping one column doesn't drag its neighbors. */
  unitSystem: UnitSystem;
  /** Flip just this column between metric and imperial. Wired to a
   *  per-column override map in the parent. */
  onUnitToggle: () => void;
  onFilterChange: (filter: FilterCriterion | null) => void;
  onSort: () => void;
  onRemove: () => void;
  onResizeStart: (e: React.MouseEvent) => void;
}

const SLIDER_OPERATORS: ComparisonOperator[] = ['>=', '<'];

const getNested = (obj: unknown, path: string): unknown => {
  if (!obj || typeof obj !== 'object') return undefined;
  const parts = path.split('.');
  let v: any = obj;
  for (const p of parts) {
    if (v == null) return undefined;
    v = v[p];
  }
  return v;
};

const numericFromValue = (val: unknown): number | null => {
  if (typeof val === 'number') return val;
  if (val && typeof val === 'object') {
    const o = val as { value?: unknown; min?: unknown; max?: unknown };
    if (typeof o.value === 'number') return o.value;
    if (typeof o.min === 'number' && typeof o.max === 'number') {
      return (o.min + o.max) / 2;
    }
  }
  return null;
};

const sniffUnit = (val: unknown): string | null => {
  if (val && typeof val === 'object' && 'unit' in val) {
    const u = (val as { unit?: unknown }).unit;
    if (typeof u === 'string') return u;
  }
  return null;
};

export default function ColumnHeader({
  attribute,
  label,
  products,
  allProducts,
  filter,
  sortConfig,
  sortIndex,
  totalSorts,
  width,
  unitSystem,
  onUnitToggle,
  onFilterChange,
  onSort,
  onRemove,
  onResizeStart,
}: ColumnHeaderProps) {
  const sliderTrackRef = useRef<HTMLDivElement>(null);
  const sliderInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [editingValue, setEditingValue] = useState(false);
  const [valueDraft, setValueDraft] = useState('');

  // Slider scale comes from the *unfiltered* source so the track doesn't
  // shrink as the user dials in other filters. Lets the user always
  // drag the thumb back out — and matches the histogram's anchored
  // x-range below.
  const rangeInfo = useMemo(() => {
    const values: number[] = [];
    let attrUnit: string | null = null;
    for (const p of allProducts) {
      const raw = getNested(p, attribute.key);
      if (raw == null) continue;
      const n = numericFromValue(raw);
      if (n != null && Number.isFinite(n)) {
        values.push(n);
        if (!attrUnit) attrUnit = sniffUnit(raw);
      }
    }
    if (values.length === 0) return null;
    values.sort((a, b) => a - b);
    return {
      min: values[0],
      max: values[values.length - 1],
      sortedValues: values,
      unit: attrUnit ?? attribute.unit ?? '',
    };
  }, [allProducts, attribute.key, attribute.unit]);

  const isSliderEligible =
    (attribute.type === 'object' || attribute.type === 'range') && rangeInfo !== null;

  const operator: ComparisonOperator =
    (filter?.operator as ComparisonOperator) ?? '>=';
  const filterValue =
    typeof filter?.value === 'number' ? (filter.value as number) : null;

  const sliderPercent = useMemo(() => {
    if (!rangeInfo) return 0;
    if (filterValue == null) {
      return operator === '<' || operator === '<=' ? 100 : 0;
    }
    const n = rangeInfo.sortedValues.length;
    if (n <= 1) return 0;
    let lo = 0;
    let hi = n - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (rangeInfo.sortedValues[mid] < filterValue) lo = mid + 1;
      else hi = mid;
    }
    let idx = lo;
    if (
      lo > 0 &&
      Math.abs(rangeInfo.sortedValues[lo - 1] - filterValue) <
        Math.abs(rangeInfo.sortedValues[lo] - filterValue)
    ) {
      idx = lo - 1;
    }
    return (idx / (n - 1)) * 100;
  }, [rangeInfo, filterValue, operator]);

  const updateFromPointer = (clientX: number) => {
    if (!rangeInfo) return;
    const track = sliderTrackRef.current;
    if (!track) return;
    const rect = track.getBoundingClientRect();
    if (rect.width === 0) return;
    const t = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    const n = rangeInfo.sortedValues.length;
    if (n <= 1) return;
    const idx = Math.round(t * (n - 1));
    const newValue = rangeInfo.sortedValues[idx];
    if (filter) {
      if (filter.value !== newValue) {
        onFilterChange({ ...filter, value: newValue });
      }
    } else {
      onFilterChange({
        attribute: attribute.key,
        displayName: label,
        mode: 'include',
        operator: '>=',
        value: newValue,
      });
    }
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!rangeInfo) return;
    e.preventDefault();
    e.stopPropagation();
    sliderTrackRef.current?.setPointerCapture(e.pointerId);
    setIsDragging(true);
    updateFromPointer(e.clientX);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    updateFromPointer(e.clientX);
  };

  const handlePointerEnd = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    sliderTrackRef.current?.releasePointerCapture(e.pointerId);
    setIsDragging(false);
  };

  const handleSliderKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!rangeInfo) return;
    const n = rangeInfo.sortedValues.length;
    if (n <= 1) return;
    const currentIdx =
      filterValue != null ? rangeInfo.sortedValues.indexOf(filterValue) : -1;
    const idx = currentIdx === -1 ? 0 : currentIdx;
    let next = idx;
    switch (e.key) {
      case 'ArrowRight':
      case 'ArrowUp':
        next = Math.min(n - 1, idx + 1);
        break;
      case 'ArrowLeft':
      case 'ArrowDown':
        next = Math.max(0, idx - 1);
        break;
      case 'Home':
        next = 0;
        break;
      case 'End':
        next = n - 1;
        break;
      case 'PageUp':
        next = Math.min(n - 1, idx + Math.max(1, Math.round(n / 10)));
        break;
      case 'PageDown':
        next = Math.max(0, idx - Math.max(1, Math.round(n / 10)));
        break;
      default:
        return;
    }
    e.preventDefault();
    const newValue = rangeInfo.sortedValues[next];
    if (filter) {
      onFilterChange({ ...filter, value: newValue });
    } else {
      onFilterChange({
        attribute: attribute.key,
        displayName: label,
        mode: 'include',
        operator: '>=',
        value: newValue,
      });
    }
  };

  const cycleOperator = () => {
    const idx = SLIDER_OPERATORS.indexOf(operator);
    const next = SLIDER_OPERATORS[(idx + 1) % SLIDER_OPERATORS.length];
    if (filter) {
      onFilterChange({ ...filter, operator: next });
    } else if (rangeInfo) {
      const seedIdx = next === '<' ? rangeInfo.sortedValues.length - 1 : 0;
      onFilterChange({
        attribute: attribute.key,
        displayName: label,
        mode: 'include',
        operator: next,
        value: rangeInfo.sortedValues[seedIdx],
      });
    }
  };

  const commitOverride = () => {
    if (!rangeInfo) {
      setEditingValue(false);
      return;
    }
    const trimmed = valueDraft.trim();
    if (trimmed === '') {
      setEditingValue(false);
      return;
    }
    const parsed = parseFloat(trimmed);
    if (Number.isNaN(parsed)) {
      setEditingValue(false);
      return;
    }
    const canonical = rangeInfo.unit
      ? toCanonical(parsed, rangeInfo.unit, unitSystem)
      : parsed;
    if (filter) {
      onFilterChange({ ...filter, value: canonical });
    } else {
      onFilterChange({
        attribute: attribute.key,
        displayName: label,
        mode: 'include',
        operator: '>=',
        value: canonical,
      });
    }
    setEditingValue(false);
  };

  const cancelOverride = () => {
    setEditingValue(false);
    setValueDraft('');
  };

  useEffect(() => {
    if (editingValue) sliderInputRef.current?.focus();
  }, [editingValue]);

  // Click the unit text to flip *this* column's unit system. Other
  // columns keep whatever unit they had — overrides are per-column.
  const handleUnitClick = () => {
    onUnitToggle();
  };

  const headerClasses =
    'product-grid-header-item column-header' + (filter ? ' has-filter' : '');

  const dispCurrent =
    rangeInfo && filterValue != null
      ? toDisplay(filterValue, rangeInfo.unit, unitSystem)
      : null;
  const dispUnit = rangeInfo?.unit ? displayUnit(rangeInfo.unit, unitSystem) : '';
  const intLikeUnit = rangeInfo ? isIntegerUnit(rangeInfo.unit) : false;

  return (
    <div className={headerClasses} style={{ width }}>
      <button
        className="column-remove-btn"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        title="Hide column"
      >
        <svg
          width="10"
          height="10"
          viewBox="0 0 10 10"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          aria-hidden="true"
        >
          <path d="M2 2 L8 8 M8 2 L2 8" />
        </svg>
      </button>

      {/* Histogram strip — anchored to allProducts for a stable x-range,
       * but the bar heights come from the filtered set so the user sees
       * which slice their filter has selected. */}
      {isSliderEligible && (
        <div className="column-header-histogram">
          <DistributionChart
            products={products}
            attribute={attribute.key}
            title=""
            attributeType={attribute.type}
            allProducts={allProducts}
          />
        </div>
      )}

      {/* Sortable label row. Click target is the label text itself, with
       * a hover underline + cursor:pointer so the affordance is obvious.
       * The rest of the header (slider, readout) is interactive in its
       * own right and doesn't trigger sort. */}
      <button
        type="button"
        className="column-header-sort"
        onClick={onSort}
        title="Click to sort • click again to reverse, again to clear"
      >
        <span className="column-header-label-text">{label}</span>
        <span className="sort-indicator">
          {sortConfig?.direction === 'asc' && '↑'}
          {sortConfig?.direction === 'desc' && '↓'}
          {sortConfig && totalSorts > 1 && (
            <span className="sort-order">{sortIndex + 1}</span>
          )}
        </span>
      </button>

      {isSliderEligible && rangeInfo && (
        <>
          <div className="column-header-slider">
            <div
              ref={sliderTrackRef}
              className={`filter-slider-track-container${
                isDragging ? ' is-dragging' : ''
              }`}
              role="slider"
              tabIndex={0}
              aria-valuemin={rangeInfo.min}
              aria-valuemax={rangeInfo.max}
              aria-valuenow={filterValue ?? rangeInfo.min}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerEnd}
              onPointerCancel={handlePointerEnd}
              onKeyDown={handleSliderKeyDown}
            >
              <div className="filter-slider-rail" />
              <div
                className="filter-slider-active-region"
                style={{
                  left:
                    operator === '<' || operator === '<=' ? '0%' : `${sliderPercent}%`,
                  right:
                    operator === '<' || operator === '<='
                      ? `${100 - sliderPercent}%`
                      : '0%',
                }}
              />
              <div
                className="filter-slider-thumb"
                style={{ left: `${sliderPercent}%` }}
              />
            </div>
          </div>

          {/* Single-line readout: operator · number · unit. Each piece is
           * a click target with a different action — operator cycles >=/<,
           * number opens the type-edit input, unit toggles imperial/metric. */}
          <div className="column-header-readout">
            <button
              type="button"
              className="readout-operator"
              onClick={cycleOperator}
              title={`Operator ${operator} — click to flip (>= ↔ <)`}
              aria-label={`Filter operator ${operator}`}
            >
              {operator === '>=' ? '≥' : operator === '<=' ? '≤' : operator}
            </button>
            {editingValue ? (
              <input
                ref={sliderInputRef}
                type="number"
                className="readout-value-input"
                value={valueDraft}
                step="any"
                onChange={(e) => setValueDraft(e.target.value)}
                onBlur={commitOverride}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    commitOverride();
                  } else if (e.key === 'Escape') {
                    e.preventDefault();
                    cancelOverride();
                  }
                }}
                aria-label="Override slider with typed value"
              />
            ) : (
              <button
                type="button"
                className="readout-value"
                onClick={() => {
                  if (dispCurrent != null) {
                    setValueDraft(
                      intLikeUnit
                        ? String(Math.round(dispCurrent))
                        : String(Number(dispCurrent.toFixed(2))),
                    );
                  } else {
                    setValueDraft('');
                  }
                  setEditingValue(true);
                }}
                title="Click to type an exact value"
              >
                {dispCurrent != null
                  ? intLikeUnit
                    ? Math.round(dispCurrent).toLocaleString()
                    : dispCurrent.toFixed(1)
                  : 'any'}
              </button>
            )}
            {dispUnit && (
              <button
                type="button"
                className="readout-unit"
                onClick={handleUnitClick}
                title={`Click to switch units (currently ${unitSystem})`}
                aria-label={`Unit ${dispUnit} — click to swap unit system`}
              >
                {dispUnit}
              </button>
            )}
          </div>
        </>
      )}

      <div
        className="col-resize-handle"
        onMouseDown={(e) => {
          e.stopPropagation();
          onResizeStart(e);
        }}
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}
