/**
 * Product list component with advanced filtering and sorting
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import { useApp } from '../context/AppContext';
import { ProductType, Product } from '../types/models';
import { FilterCriterion, SortConfig, applyFilters, sortProducts, getAttributesForType, deriveAttributesFromRecords, mergeAttributesByKey, AttributeMetadata, getAvailableOperators, buildDefaultFiltersForType, DEFAULT_FILTER_FLOOR_PERCENTILE } from '../types/filters';
// Column order is authored in types/columnOrder.ts — edit that file to
// change what columns appear and in what order.
import { orderColumnAttributes } from '../types/columnOrder';
import { formatValue, computeAutoColumnWidths } from '../utils/formatting';
import { displayUnit, convertValueUnit, convertMinMaxUnit } from '../utils/unitConversion';
import { numericFromValue } from '../utils/filterValues';
import { useColumnResize } from '../utils/hooks';
import {
  safeLoad,
  safeSave,
  isStringArray,
} from '../utils/localStorage';
import FilterBar from './FilterBar';
import ProductDetailModal from './ProductDetailModal';
import AttributeSelector from './AttributeSelector';
import Dropdown from './Dropdown';
import { ADJACENT_TYPES, BuildSlot, check as compatCheck } from '../utils/compat';

export default function ProductList() {
  const { products, categories, loading, error, loadProducts, loadCategories, unitSystem, build, compatibleOnly, setCompatibleOnly, rowDensity } = useApp();
  const [productType, setProductType] = useState<ProductType>(null);
  const [filters, setFilters] = useState<FilterCriterion[]>([]);
  const [sorts, setSorts] = useState<SortConfig[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [clickPosition, setClickPosition] = useState<{ x: number; y: number } | null>(null);
  const [showSortSelector, setShowSortSelector] = useState(false);
  const [columnSelectorCursor, setColumnSelectorCursor] = useState<{ x: number; y: number } | null>(null);
  const [itemsPerPage, setItemsPerPage] = useState<number>(25);
  const [currentPage, setCurrentPage] = useState<number>(1);
  // Column visibility model — two sets, because default visibility
  // depends on the attribute's *kind*:
  //
  // - ValueUnit / MinMaxUnit columns (numeric with a unit) are visible
  //   by default. User hides them via the × button; stored in
  //   `userHiddenKeys`.
  // - Every other kind (strings, booleans, arrays, bare ints/floats)
  //   is hidden by default — too noisy in a spec table — and must be
  //   explicitly pulled out of the "+ N hidden" dropdown. Those opt-in
  //   restores are stored in `userRestoredKeys`.
  //
  // Both sets persist across sessions. The old 'productListHiddenColumns'
  // key now stores userHiddenKeys.
  const [userHiddenKeys, setUserHiddenKeys] = useState<string[]>(() =>
    safeLoad('productListHiddenColumns', isStringArray, []),
  );
  useEffect(() => {
    safeSave('productListHiddenColumns', userHiddenKeys);
  }, [userHiddenKeys]);

  const [userRestoredKeys, setUserRestoredKeys] = useState<string[]>(() =>
    safeLoad('productListRestoredColumns', isStringArray, []),
  );
  useEffect(() => {
    safeSave('productListRestoredColumns', userRestoredKeys);
  }, [userRestoredKeys]);

  // Drag-to-reorder column session state. Intentionally NOT persisted —
  // every visit starts in the canonical order from columnOrder.ts; users
  // can rearrange during their session and a refresh resets the view.
  // `sessionColumnOrder` is null until the first successful drop, then
  // becomes the user's preferred key sequence (only keys currently visible
  // are honored; new/restored columns append at the end).
  const [sessionColumnOrder, setSessionColumnOrder] = useState<string[] | null>(null);
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

  // Hard cap on simultaneously visible spec columns. Compact rows fit ten
  // before the table feels crowded; comfy is six so the row breathes
  // without horizontal scrolling. Extras spill into the restore dropdown
  // and stay individually restorable.
  const MAX_VISIBLE_COLUMNS = rowDensity === 'compact' ? 10 : 6;
  const [addColumnBtnRef, setAddColumnBtnRef] = useState<HTMLButtonElement | null>(null);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [appType, setAppType] = useState<'rotary' | 'linear' | 'z-axis'>('rotary');
  const [linearTravel, setLinearTravel] = useState<number>(0); // mm/rev
  const [loadMass, setLoadMass] = useState<number>(0); // kg (for Z-axis gravity calc)

// Floor widths (px) for the part-number column — twice the historical
// default so common 12-16 char part numbers stop truncating. The auto-
// fit helper widens further whenever the loaded data warrants it.
  const defaultPartWidth = rowDensity === 'compact' ? 240 : 320;
  const defaultColWidth = rowDensity === 'compact' ? 90 : 130;
  const { columnWidths, setColumnWidths, startResize } = useColumnResize({ part_number: defaultPartWidth });

  // Keys that should never render as their own column. `part_number` is
  // pinned as the leading column by the existing render code; the rest are
  // identity, bookkeeping, or per-record URLs that aren't useful in a
  // spec table.
  const COLUMN_EXCLUDED_KEYS = useMemo(
    () =>
      new Set<string>([
        'part_number',
        'datasheet_url',
        'pages',
        'PK',
        'SK',
        'product_id',
        'product_type',
        'msrp_source_url',
        'msrp_fetched_at',
      ]),
    [],
  );

  // Full ordered column list — authored order from types/columnOrder.ts
  // first, then alphabetical for any unlisted keys. Excludes identity/
  // metadata keys. Does NOT yet filter by hidden set; we keep the full
  // list so AttributeSelector can tell what's hideable vs hidden.
  // `visibleColumnAttributes` below is the filtered view.
  const columnAttributes = useMemo<AttributeMetadata[]>(() => {
    if (!productType) return [];
    const staticAttrs = getAttributesForType(productType);
    const derivedAttrs = deriveAttributesFromRecords(products, productType);
    const merged = mergeAttributesByKey(staticAttrs, derivedAttrs).filter(
      a => !COLUMN_EXCLUDED_KEYS.has(a.key),
    );
    return orderColumnAttributes(merged, productType);
  }, [productType, products, COLUMN_EXCLUDED_KEYS]);

  // Columns actually rendered in the table. Default rule:
  // - `userRestored` → always visible (explicit opt-in)
  // - `userHidden`   → always hidden
  // - `defaultVisible === true` → visible (expert override)
  // - `defaultVisible === false` → hidden (expert override, e.g. a
  //   ValueUnit motor spec that's motor-designer-only)
  // - otherwise fall through to the kind-based default: ValueUnit /
  //   MinMaxUnit (nested:true) visible, everything else hidden.
  // Then clamp to MAX_VISIBLE_COLUMNS; columns past the cap spill into
  // the restore dropdown.
  const visibleColumnAttributes = useMemo<AttributeMetadata[]>(() => {
    const shown = columnAttributes.filter(a => {
      if (userHiddenKeys.includes(a.key)) return false;
      if (userRestoredKeys.includes(a.key)) return true;
      if (a.defaultVisible === true) return true;
      if (a.defaultVisible === false) return false;
      return a.nested === true;
    });
    const capped = shown.slice(0, MAX_VISIBLE_COLUMNS);
    // No drag-reorder yet → canonical order from columnOrder.ts.
    if (!sessionColumnOrder) return capped;
    // Apply user's drag order on top: keys named in sessionColumnOrder
    // appear in that sequence; anything new (a column the user later
    // restored / a derived field that just appeared in records) is
    // appended in canonical order so it doesn't silently disappear.
    const byKey = new Map(capped.map(a => [a.key, a]));
    const used = new Set<string>();
    const reordered: AttributeMetadata[] = [];
    for (const key of sessionColumnOrder) {
      const attr = byKey.get(key);
      if (attr) {
        reordered.push(attr);
        used.add(key);
      }
    }
    for (const attr of capped) {
      if (!used.has(attr.key)) reordered.push(attr);
    }
    return reordered;
  }, [columnAttributes, userHiddenKeys, userRestoredKeys, MAX_VISIBLE_COLUMNS, sessionColumnOrder]);

  // Reset session order when product type changes — a drag-reorder for
  // motors shouldn't carry over to drives.
  useEffect(() => {
    setSessionColumnOrder(null);
    setDragKey(null);
    setDropIndex(null);
  }, [productType]);

  // ---- Column drag-and-drop handlers ----
  // Order doesn't change until drop, so the table body doesn't reflow
  // during the drag. Dropping outside any header (or pressing Escape)
  // fires `dragend` without a prior `drop`, which clears state and
  // leaves the original order intact.
  const handleColumnDragStart = (e: React.DragEvent<HTMLDivElement>, key: string) => {
    setDragKey(key);
    setDropIndex(null);
    e.dataTransfer.effectAllowed = 'move';
    // Some browsers refuse to start a drag without dataTransfer payload.
    e.dataTransfer.setData('text/plain', key);
  };

  const handleColumnDragOver = (e: React.DragEvent<HTMLDivElement>, hoveredIndex: number) => {
    if (dragKey === null) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const rect = e.currentTarget.getBoundingClientRect();
    const onLeftHalf = e.clientX < rect.left + rect.width / 2;
    const next = onLeftHalf ? hoveredIndex : hoveredIndex + 1;
    setDropIndex(prev => (prev === next ? prev : next));
  };

  const handleColumnDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (dragKey === null || dropIndex === null) {
      setDragKey(null);
      setDropIndex(null);
      return;
    }
    const currentOrder = visibleColumnAttributes.map(a => a.key);
    const fromIndex = currentOrder.indexOf(dragKey);
    if (fromIndex === -1) {
      setDragKey(null);
      setDropIndex(null);
      return;
    }
    // Insertion semantics: dropIndex is the insertion slot in the original
    // array. After removing the dragged key, every slot at or after
    // fromIndex shifts left by one.
    const without = currentOrder.filter((_, i) => i !== fromIndex);
    const insertAt = dropIndex > fromIndex ? dropIndex - 1 : dropIndex;
    if (insertAt === fromIndex) {
      setDragKey(null);
      setDropIndex(null);
      return;
    }
    without.splice(insertAt, 0, dragKey);
    setSessionColumnOrder(without);
    setDragKey(null);
    setDropIndex(null);
  };

  const handleColumnDragEnd = () => {
    setDragKey(null);
    setDropIndex(null);
  };

  // Restore-dropdown candidates: everything the user could bring back —
  // explicit hides, cap overflow, and the hidden-by-default non-unit
  // kinds (strings, booleans, arrays, bare numbers).
  const hiddenColumnAttributes = useMemo<AttributeMetadata[]>(() => {
    const visibleKeys = new Set(visibleColumnAttributes.map(a => a.key));
    return columnAttributes.filter(a => !visibleKeys.has(a.key));
  }, [columnAttributes, visibleColumnAttributes]);

  // Auto-fit defaults from data: each column's width = P90 of its formatted-
  // value lengths in the loaded rows, header label as the floor, with
  // `part_number` floored at 2x so it always reveals more characters than
  // the rest. Computed fresh whenever the productType, visible-column set,
  // or loaded data changes — but a user's manual resize (tracked in
  // columnWidths) wins and is preserved across these transitions.
  useEffect(() => {
    if (!productType) return;
    const cols = [
      { key: 'part_number', displayName: 'Part Number' },
      ...visibleColumnAttributes.map(a => ({ key: a.key, displayName: a.displayName })),
    ];
    const auto = computeAutoColumnWidths({
      rows: products as unknown as Array<Record<string, unknown>>,
      columns: cols,
      density: rowDensity,
      unitSystem,
      perKeyMin: { part_number: defaultPartWidth },
    });
    setColumnWidths(prev => {
      const next: Record<string, number> = {};
      for (const col of cols) {
        next[col.key] = prev[col.key] ?? auto[col.key]
          ?? (col.key === 'part_number' ? defaultPartWidth : defaultColWidth);
      }
      return next;
    });
  }, [productType, visibleColumnAttributes, products, unitSystem, defaultPartWidth, defaultColWidth, setColumnWidths]);

  // Density flip → clobber to the new mode's auto-fit defaults so the
  // bumped px-per-char and padding actually take effect. Manual resizes
  // within a mode are preserved by the effect above; they only reset on
  // an intentional density toggle.
  useEffect(() => {
    if (!productType) return;
    const cols = [
      { key: 'part_number', displayName: 'Part Number' },
      ...visibleColumnAttributes.map(a => ({ key: a.key, displayName: a.displayName })),
    ];
    const auto = computeAutoColumnWidths({
      rows: products as unknown as Array<Record<string, unknown>>,
      columns: cols,
      density: rowDensity,
      unitSystem,
      perKeyMin: { part_number: defaultPartWidth },
    });
    setColumnWidths(() => {
      const next: Record<string, number> = {};
      for (const col of cols) {
        next[col.key] = auto[col.key]
          ?? (col.key === 'part_number' ? defaultPartWidth : defaultColWidth);
      }
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowDensity]);

  // Load products and categories when product type changes or on mount
  useEffect(() => {
    if (productType !== null) {
      loadProducts(productType);
    }
    if (categories.length === 0) {
      loadCategories();
    }
  }, [productType, loadProducts, loadCategories]);

  // Seed default filter chips with a P10 value once products load. Runs
  // once per product-type via seededTypeRef so a user who later clears or
  // adjusts a chip's value doesn't get it re-populated. We override even
  // non-undefined values on this one-shot run because FilterChip's own
  // auto-init also seeds at P10; the per-type seed wins to guarantee the
  // bottom decile is excluded for the chips we ship enabled by default.
  // The percentile lives in DEFAULT_FILTER_FLOOR_PERCENTILE.
  const seededTypeRef = useRef<ProductType | null>(null);
  useEffect(() => {
    if (!productType || products.length === 0) return;
    if (seededTypeRef.current === productType) return;
    const typeAttrs = getAttributesForType(productType);
    const isDefaultKey = (key: string) =>
      typeAttrs.some(a => a.key === key && a.defaultFilter);
    setFilters(prev => {
      let mutated = false;
      const next = prev.map(f => {
        if (!isDefaultKey(f.attribute)) return f;
        const values: number[] = [];
        for (const product of products) {
          const raw = (product as unknown as Record<string, unknown>)[f.attribute];
          let n: number | null = null;
          if (typeof raw === 'number') n = raw;
          else if (raw && typeof raw === 'object') {
            const o = raw as { value?: unknown; min?: unknown; max?: unknown };
            if (typeof o.value === 'number') n = o.value;
            else if (typeof o.min === 'number' && typeof o.max === 'number') n = (o.min + o.max) / 2;
          }
          if (n !== null && Number.isFinite(n)) values.push(n);
        }
        if (values.length === 0) return f;
        values.sort((a, b) => a - b);
        const idx = Math.min(values.length - 1,
          Math.floor(values.length * DEFAULT_FILTER_FLOOR_PERCENTILE));
        mutated = true;
        return { ...f, value: values[idx] };
      });
      return mutated ? next : prev;
    });
    seededTypeRef.current = productType;
  }, [productType, products]);

  // Add keyboard shortcut for opening filter (Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const addButton = document.querySelector('.filter-bar-button.primary') as HTMLButtonElement;
        addButton?.click();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Handle product type change. Seed the filter list with this type's
  // curated defaults (e.g. motor → rated_torque, rated_speed) so the
  // sidebar opens with the chips an integrator almost always reaches
  // for. Chips land valueless; the user dials in the constraint.
  // Sort starts empty — rows render in the catalog's natural order
  // until the user clicks a column header.
  const handleProductTypeChange = (newType: ProductType) => {
    setProductType(newType);
    setFilters(buildDefaultFiltersForType(newType));
    setSorts([]);
    setAppType('rotary');
    setLinearTravel(0);
    setLoadMass(0);
  };

  // Torque/speed keys — used for linear-mode display conversions.
  const TORQUE_KEYS = ['rated_torque', 'peak_torque'];
  const SPEED_KEYS = ['rated_speed'];

  // Linear motion conversion helpers
  const isLinearMode = (appType === 'linear' || appType === 'z-axis') && linearTravel > 0;
  const GRAVITY = 9.81; // m/s²

  // Convert RPM ValueUnit to linear speed (mm/s)
  const rpmToLinearSpeed = (value: any): any => {
    if (!value || !linearTravel) return value;
    if (typeof value === 'object' && 'value' in value && typeof value.value === 'number') {
      return { value: parseFloat(((value.value / 60) * linearTravel).toPrecision(4)), unit: 'mm/s' };
    }
    if (typeof value === 'object' && 'min' in value && 'max' in value) {
      return {
        min: value.min != null ? parseFloat(((value.min / 60) * linearTravel).toPrecision(4)) : value.min,
        max: value.max != null ? parseFloat(((value.max / 60) * linearTravel).toPrecision(4)) : value.max,
        unit: 'mm/s'
      };
    }
    return value;
  };

  // Convert torque (Nm) ValueUnit to thrust force (N)
  // F = T * 2π / lead (lead in meters). Assumes 100% screw efficiency —
  // simpler default; revisit if real-world losses become material to the
  // selection workflow.
  const torqueToThrust = (value: any): any => {
    if (!value || !linearTravel) return value;
    const factor = (2 * Math.PI) / (linearTravel * 0.001);
    if (typeof value === 'object' && 'value' in value && typeof value.value === 'number') {
      return { value: parseFloat((value.value * factor).toPrecision(4)), unit: 'N' };
    }
    if (typeof value === 'object' && 'min' in value && 'max' in value) {
      return {
        min: value.min != null ? parseFloat((value.min * factor).toPrecision(4)) : value.min,
        max: value.max != null ? parseFloat((value.max * factor).toPrecision(4)) : value.max,
        unit: 'N'
      };
    }
    return value;
  };

  // Build-aware compat narrowing. When the user has anchored part of their
  // motion-system build and the active type is adjacent to one of those
  // anchors, drop products that strict-fail compat. Soft-partials (missing
  // data) stay visible — we can't prove them incompatible.
  const compatAnchors = useMemo(() => {
    if (!productType || !ADJACENT_TYPES[productType]) return [];
    return ADJACENT_TYPES[productType]
      .map(t => build[t as BuildSlot])
      .filter((p): p is Product => !!p);
  }, [productType, build]);

  const compatFilterActive = compatibleOnly && compatAnchors.length > 0;

  const compatNarrowed = useMemo(() => {
    if (!compatFilterActive) return products;
    return products.filter(p => {
      for (const anchor of compatAnchors) {
        try {
          if (compatCheck(p, anchor).status === 'fail') return false;
        } catch {
          // Pair unsupported — leave the row visible rather than silently hiding.
        }
      }
      return true;
    });
  }, [products, compatAnchors, compatFilterActive]);

  const compatHiddenCount = compatFilterActive ? products.length - compatNarrowed.length : 0;

  // Linear-mode transform applied *before* filter/sort so the filter
  // pane's sliders, the table cells, and the sort all operate on the
  // same units (N / mm/s) when linear mode is on. Compat-check stays
  // upstream because it expects canonical Nm/rpm.
  const linearizedSource = useMemo(() => {
    if (!isLinearMode) return compatNarrowed;
    return compatNarrowed.map(p => {
      const copy = { ...p } as any;
      for (const key of SPEED_KEYS) {
        if (copy[key]) copy[key] = rpmToLinearSpeed(copy[key]);
      }
      for (const key of TORQUE_KEYS) {
        if (copy[key]) copy[key] = torqueToThrust(copy[key]);
      }
      return copy as Product;
    });
  }, [compatNarrowed, isLinearMode, linearTravel]);

  const filteredProducts = useMemo(() => {
    return applyFilters(linearizedSource, filters);
  }, [linearizedSource, filters]);

  // Apply sorting to filtered products
  const sortedProducts = useMemo(
    () => sortProducts(filteredProducts, sorts.length > 0 ? sorts : null),
    [filteredProducts, sorts]
  );

  // The display set is now identical to the sorted set — linearization
  // already happened upstream. Kept as an alias so call sites read the
  // same as before.
  const displayProducts = sortedProducts;

  // Paginate products
  const paginatedProducts = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return displayProducts.slice(startIndex, endIndex);
  }, [displayProducts, currentPage, itemsPerPage]);

  const totalPages = Math.ceil(displayProducts.length / itemsPerPage);

  // Reset to page 1 when filters, sorts, or items per page change
  useEffect(() => {
    setCurrentPage(1);
  }, [filters, sorts, itemsPerPage]);

  // When the linear-mode flips (or travel changes the unit scale), the
  // stored filter values for torque/speed are no longer comparable to
  // the new product unit (Nm ↔ N, rpm ↔ mm/s). Clear values *and* swap
  // each chip's displayName so the label matches the unit it now
  // operates in (Rated Torque ↔ Rated Thrust, Rated Speed ↔ Linear
  // Speed). The chip itself stays put.
  useEffect(() => {
    const linearLabel = (key: string): string | null => {
      if (key === 'rated_torque') return 'Rated Thrust';
      if (key === 'peak_torque') return 'Peak Thrust';
      if (key === 'rated_speed') return 'Linear Speed';
      return null;
    };
    const rotaryLabel = (key: string): string | null => {
      if (key === 'rated_torque') return 'Rated Torque';
      if (key === 'peak_torque') return 'Peak Torque';
      if (key === 'rated_speed') return 'Rated Speed';
      return null;
    };
    setFilters(current => {
      let changed = false;
      const next = current.map(f => {
        const baseKey = f.attribute.split('.')[0];
        if (!TORQUE_KEYS.includes(baseKey) && !SPEED_KEYS.includes(baseKey)) {
          return f;
        }
        const targetName = isLinearMode ? linearLabel(baseKey) : rotaryLabel(baseKey);
        const needsNameSwap = targetName !== null && targetName !== f.displayName;
        const needsValueReset = f.value !== undefined;
        if (!needsNameSwap && !needsValueReset) return f;
        changed = true;
        return {
          ...f,
          value: undefined,
          displayName: targetName ?? f.displayName,
        };
      });
      return changed ? next : current;
    });
  }, [isLinearMode, linearTravel]);

  // Column headers with linear-mode label/unit overrides for SPEED_KEYS
  // and TORQUE_KEYS (thrust/force view for linear actuators). Unit
  // strings flip through `displayUnit()` so e.g. Nm → in·lb when the
  // global unit toggle is set to imperial. Linear-mode units (mm/s, N)
  // also flip for consistency.
  const getColumnHeaders = (): Array<{ key: string; label: string; unit: string | null }> => {
    return visibleColumnAttributes.map(attr => {
      let label = attr.displayName;
      let unit: string | null = attr.unit || null;
      if (isLinearMode) {
        if (SPEED_KEYS.includes(attr.key)) {
          label = 'Linear Speed';
          unit = 'mm/s';
        } else if (TORQUE_KEYS.includes(attr.key)) {
          label = attr.key === 'peak_torque' ? 'Peak Thrust' : 'Rated Thrust';
          unit = 'N';
        }
      }
      return { key: attr.key, label, unit: unit ? displayUnit(unit, unitSystem) : null };
    });
  };

  // Extract just the numeric value from a spec (no unit). Converts
  // through the active unit system so imperial mode shows imperial
  // numbers in the table cells.
  const extractNumericOnly = (value: any): string | null => {
    if (!value) return null;

    if (typeof value === 'number') return String(value);
    if (typeof value === 'string') return value;

    if (typeof value === 'object') {
      if ('value' in value && value.value !== null && value.value !== undefined) {
        if ('unit' in value) {
          const c = convertValueUnit(value, unitSystem);
          return String(c.value);
        }
        return String(value.value);
      }

      const hasMin = 'min' in value && value.min !== null && value.min !== undefined;
      const hasMax = 'max' in value && value.max !== null && value.max !== undefined;

      if (hasMin && hasMax) {
        if ('unit' in value) {
          const c = convertMinMaxUnit(value, unitSystem);
          return `${c.min}-${c.max}`;
        }
        return `${value.min}-${value.max}`;
      } else if (hasMin) {
        if ('unit' in value) {
          const c = convertValueUnit({ value: value.min, unit: value.unit }, unitSystem);
          return String(c.value);
        }
        return String(value.min);
      } else if (hasMax) {
        if ('unit' in value) {
          const c = convertValueUnit({ value: value.max, unit: value.unit }, unitSystem);
          return String(c.value);
        }
        return String(value.max);
      }
    }

    return null;
  };

  // Min/max for each filtered numeric attribute across the visible result set.
  // Drives the per-cell highlight gradient — see getProximityColor.
  const filteredAttrRanges = useMemo(() => {
    const map = new Map<string, { min: number; max: number }>();
    for (const filter of filters) {
      if (filter.value === undefined || filter.operator === '!=') continue;
      const path = filter.attribute;
      const [baseAttr, ...rest] = path.split('.');
      const nestedKeys = rest;
      let min = Infinity;
      let max = -Infinity;
      for (const p of filteredProducts) {
        const root = (p as any)[baseAttr];
        if (root == null) continue;
        const sub = nestedKeys.length === 0
          ? root
          : nestedKeys.reduce((acc: any, k) => (acc == null ? acc : acc[k]), root);
        const n = numericFromValue(sub);
        if (n == null || !Number.isFinite(n)) continue;
        if (n < min) min = n;
        if (n > max) max = n;
      }
      if (Number.isFinite(min) && Number.isFinite(max)) {
        map.set(path, { min, max });
      }
    }
    return map;
  }, [filters, filteredProducts]);

  // Tint a cell in a filtered column based on where its value sits in the
  // visible result set. Direction follows the operator: `>`/`>=` brightens
  // high values, `<`/`<=` brightens low values, `=` brightens values nearest
  // the filter value. Opacity is a hint, not a banner.
  const getProximityColor = (attribute: string, productValue: any): string => {
    const filter = filters.find(f => f.attribute === attribute || f.attribute.startsWith(attribute + '.'));
    if (!filter || filter.operator === '!=') return '';

    let numericProductValue: number | null = null;
    if (filter.attribute === attribute) {
      numericProductValue = numericFromValue(productValue);
    } else if (filter.attribute.startsWith(attribute + '.')) {
      const nestedKey = filter.attribute.split('.').slice(1).join('.');
      if (nestedKey && productValue && typeof productValue === 'object') {
        const sub = nestedKey.split('.').reduce((acc: any, k) => (acc == null ? acc : acc[k]), productValue);
        numericProductValue = numericFromValue(sub);
      }
    }
    if (numericProductValue === null) return '';

    const range = filteredAttrRanges.get(filter.attribute);
    const span = range ? range.max - range.min : 0;
    const pct = span > 0 && range
      ? Math.max(0, Math.min(1, (numericProductValue - range.min) / span))
      : 0.5;

    const numericFilterValue = numericFromValue(filter.value);

    let intensity: number;
    if (filter.operator === '=' && numericFilterValue !== null && numericFilterValue !== 0) {
      const percentDiff = Math.abs((numericProductValue - numericFilterValue) / numericFilterValue);
      intensity = Math.max(0, 1 - percentDiff * 5);
    } else if (filter.operator === '<' || filter.operator === '<=') {
      intensity = 1 - pct;
    } else {
      intensity = pct;
    }

    const opacity = 0.04 + intensity * 0.16;
    return `hsla(45, 60%, 45%, ${opacity.toFixed(3)})`;
  };

  const isSortedAttribute = (attribute: string): boolean => {
    return sorts.some(sort => sort.attribute === attribute);
  };

  // Per-sort-attribute sorted numeric arrays over the visible (post-filter,
  // post-linear-transform) set. Used to map each cell's value to its
  // empirical CDF position, so the sort highlight gradient is robust to
  // outliers — same idea as the slider's percentile mapping in FilterChip.
  const sortedAttrValues = useMemo(() => {
    const map = new Map<string, number[]>();
    for (const s of sorts) {
      const path = s.attribute;
      const [baseAttr, ...rest] = path.split('.');
      const values: number[] = [];
      for (const p of displayProducts) {
        const root = (p as any)[baseAttr];
        if (root == null) continue;
        const sub = rest.length === 0
          ? root
          : rest.reduce((acc: any, k) => (acc == null ? acc : acc[k]), root);
        const n = numericFromValue(sub);
        if (n != null && Number.isFinite(n)) values.push(n);
      }
      if (values.length > 0) {
        values.sort((a, b) => a - b);
        map.set(path, values);
      }
    }
    return map;
  }, [sorts, displayProducts]);

  // Tint a sorted column cell by the value's percentile rank in the visible
  // set. Direction follows the sort: desc → high values brightest (they're
  // at the top), asc → low values brightest. Linear min/max scaling would
  // let a single 10× outlier compress the rest of the column into a flat
  // band; percentile rank gives every row a fair share of the gradient.
  const getSortGradientColor = (attribute: string, productValue: any): string => {
    const sort = sorts.find(
      s => s.attribute === attribute || s.attribute.startsWith(attribute + '.'),
    );
    if (!sort) return '';

    let numericProductValue: number | null = null;
    if (sort.attribute === attribute) {
      numericProductValue = numericFromValue(productValue);
    } else if (sort.attribute.startsWith(attribute + '.')) {
      const nestedKey = sort.attribute.split('.').slice(1).join('.');
      if (nestedKey && productValue && typeof productValue === 'object') {
        const sub = nestedKey.split('.').reduce(
          (acc: any, k) => (acc == null ? acc : acc[k]),
          productValue,
        );
        numericProductValue = numericFromValue(sub);
      }
    }
    if (numericProductValue === null) return '';

    const sorted = sortedAttrValues.get(sort.attribute);
    if (!sorted || sorted.length < 2) return '';

    // Binary search for empirical CDF position (mirrors valueToPosition in FilterChip).
    let lo = 0;
    let hi = sorted.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (sorted[mid] < numericProductValue) lo = mid + 1;
      else hi = mid;
    }
    let idx = lo;
    if (
      lo > 0 &&
      Math.abs(sorted[lo - 1] - numericProductValue) <
        Math.abs(sorted[lo] - numericProductValue)
    ) {
      idx = lo - 1;
    }
    const pct = idx / (sorted.length - 1);
    const intensity = sort.direction === 'asc' ? 1 - pct : pct;
    const opacity = 0.04 + intensity * 0.22;
    return `hsla(45, 70%, 50%, ${opacity.toFixed(3)})`;
  };

  const isFilteredAttribute = (attribute: string): boolean => {
    return filters.some(filter => {
      if (filter.value === undefined) return false;
      return filter.attribute === attribute || filter.attribute.startsWith(attribute + '.');
    });
  };

  const handleProductClick = (product: Product, event: React.MouseEvent) => {
    setClickPosition({ x: event.clientX, y: event.clientY });
    setSelectedProduct(product);
  };

  const handleCloseModal = () => {
    setSelectedProduct(null);
    setClickPosition(null);
  };

  const handleColumnSort = (attribute: string) => {
    const staticAttrs = getAttributesForType(productType || 'motor');
    const derivedAttrs = deriveAttributesFromRecords(products, productType);
    const allAttrs = mergeAttributesByKey(staticAttrs, derivedAttrs);
    const attributeMetadata = allAttrs.find(attr => attr.key === attribute);

    const existingSortIndex = sorts.findIndex(s => s.attribute === attribute);

    if (existingSortIndex !== -1) {
      const existingSort = sorts[existingSortIndex];
      if (existingSort.direction === 'asc') {
        const newSorts = [...sorts];
        newSorts[existingSortIndex] = { ...existingSort, direction: 'desc' };
        setSorts(newSorts);
      } else {
        setSorts(sorts.filter((_, i) => i !== existingSortIndex));
      }
    } else if (attributeMetadata) {
      setSorts([...sorts, {
        attribute: attribute,
        direction: 'asc',
        displayName: attributeMetadata.displayName
      }]);
    }

    // Mirror the sort with a filter chip for the same spec, so the user can
    // narrow as well as order in one click. Skip if a filter for this
    // attribute (or its nested children, e.g. `rated_voltage.min`) is
    // already present, and skip when we can't resolve metadata.
    if (
      attributeMetadata &&
      !filters.some(
        f => f.attribute === attribute || f.attribute.startsWith(attribute + '.'),
      )
    ) {
      const availableOperators = getAvailableOperators(products, attribute);
      const hasComparison = availableOperators.some(
        op => op === '>' || op === '>=' || op === '<' || op === '<=',
      );
      const defaultOperator = hasComparison
        ? '>='
        : availableOperators.length > 0
          ? availableOperators[0]
          : '=';
      setFilters([
        ...filters,
        {
          attribute: attribute,
          mode: 'include',
          operator: defaultOperator,
          displayName: attributeMetadata.displayName,
        },
      ]);
    }
  };

  // Hide a column: drop any active sort for it, add it to the user
  // hidden set, and clear any prior restore (non-unit kinds only —
  // unit-bearing columns can stay visible again just by removing them
  // from userHiddenKeys).
  const handleRemoveColumn = (attribute: string) => {
    setSorts(sorts.filter(s => s.attribute !== attribute));
    setUserHiddenKeys(prev => (prev.includes(attribute) ? prev : [...prev, attribute]));
    setUserRestoredKeys(prev => prev.filter(k => k !== attribute));
  };

  // Restore a column. Two paths:
  // - Unit-bearing column was user-hidden → remove from userHiddenKeys.
  // - Non-unit column (hidden by default) → add to userRestoredKeys.
  // With the cap locked (6 comfy / 10 compact), a restore that lands past
  // the cap won't appear until the user hides one of the visible columns.
  const handleAddColumn = (attribute: ReturnType<typeof getAttributesForType>[0]) => {
    setUserHiddenKeys(userHiddenKeys.filter(k => k !== attribute.key));
    if (!attribute.nested && !userRestoredKeys.includes(attribute.key)) {
      setUserRestoredKeys([...userRestoredKeys, attribute.key]);
    }
    setShowSortSelector(false);
  };



  return (
    <div className="page-split-layout">
      {/* Left side - results */}
      <main className="results-main">
        <div className="results-header">
          <div className="results-header-left">
            <div className="pagination-controls">
              <label className="pagination-label">Show:</label>
              <Dropdown<number>
                value={itemsPerPage}
                onChange={setItemsPerPage}
                ariaLabel="Items per page"
                className="pagination-select"
                options={[10, 25, 50, 100, 250, 500].map((n) => ({
                  value: n,
                  label: String(n),
                }))}
              />
            </div>
            <span className="results-count" style={{ marginLeft: '1rem' }}>
              {displayProducts.length === 0 ? '0' : `${(currentPage - 1) * itemsPerPage + 1}-${Math.min(currentPage * itemsPerPage, displayProducts.length)}`} of {displayProducts.length}
            </span>
          </div>

        </div>

        {error && (
          <div className="error" style={{ margin: '0.5rem 0' }}>
            {error}
            <button onClick={() => loadProducts(productType)} style={{ marginLeft: '0.8rem' }}>
              Retry
            </button>
          </div>
        )}

        {productType === null || (!loading && displayProducts.length === 0) ? (
          <div className="empty-state-minimal">
            <p>
              {productType === null
                ? 'Select a product type to begin'
                : products.length === 0
                ? 'No products in database'
                : 'No results match your specs'}
            </p>
          </div>
        ) : (
          <>
            {compatFilterActive && compatHiddenCount > 0 && (
              <div className="compat-filter-banner" role="status">
                <span>
                  Showing {compatNarrowed.length} of {products.length} {productType}s compatible with{' '}
                  {compatAnchors.map(a => `${a.product_type} ${a.part_number || a.manufacturer}`).join(' & ')}
                  . {compatHiddenCount} hidden.
                </span>
                <button
                  type="button"
                  className="compat-filter-banner-toggle"
                  onClick={() => setCompatibleOnly(false)}
                >
                  Show all
                </button>
              </div>
            )}
            {!compatibleOnly && compatAnchors.length > 0 && (
              <div className="compat-filter-banner" role="status">
                <span>Compatibility filter is off. Build anchors: {compatAnchors.length}.</span>
                <button
                  type="button"
                  className="compat-filter-banner-toggle"
                  onClick={() => setCompatibleOnly(true)}
                >
                  Re-enable
                </button>
              </div>
            )}
            <div className="product-grid-scroll">
            <div className={`product-grid density-${rowDensity}`}>
            {/* Column headers */}
            <div className="product-grid-headers">
              <div
                className="product-grid-header-part clickable"
                style={{ width: columnWidths['part_number'] ?? defaultPartWidth }}
                onClick={() => handleColumnSort('part_number')}
                title="Click anywhere to sort • click again to reverse, again to clear"
              >
                Part Number
                <span className="sort-indicator">
                  {sorts.find(s => s.attribute === 'part_number')?.direction === 'asc' && '↑'}
                  {sorts.find(s => s.attribute === 'part_number')?.direction === 'desc' && '↓'}
                  {sorts.some(s => s.attribute === 'part_number') && sorts.length > 1 &&
                    <span className="sort-order">{sorts.findIndex(s => s.attribute === 'part_number') + 1}</span>
                  }
                </span>
                <div className="col-resize-handle" onMouseDown={(e) => startResize('part_number', e)} />
              </div>
              {/* Spec columns — all visible columns get an × to hide
                  them; restore from the "+ Add Spec" dropdown. */}
              {(() => {
                const headers = getColumnHeaders();
                return headers.map((header, headerIndex) => {
                  const sortIndex = sorts.findIndex(s => s.attribute === header.key);
                  const isSorted = sortIndex !== -1;
                  const sortConfig = isSorted ? sorts[sortIndex] : null;
                  const isDragging = dragKey === header.key;
                  const showDropBefore = dragKey !== null && dropIndex === headerIndex;
                  const showDropAfter =
                    dragKey !== null &&
                    dropIndex === headers.length &&
                    headerIndex === headers.length - 1;

                  return (
                    <div
                      key={header.key}
                      className={
                        'product-grid-header-item clickable' +
                        (isDragging ? ' dragging' : '') +
                        (showDropBefore ? ' drop-before' : '') +
                        (showDropAfter ? ' drop-after' : '')
                      }
                      style={{ width: columnWidths[header.key] ?? defaultColWidth }}
                      title="Drag to reorder • click anywhere to sort • click again to reverse, again to clear"
                      onClick={() => handleColumnSort(header.key)}
                      draggable
                      onDragStart={(e) => handleColumnDragStart(e, header.key)}
                      onDragOver={(e) => handleColumnDragOver(e, headerIndex)}
                      onDrop={handleColumnDrop}
                      onDragEnd={handleColumnDragEnd}
                    >
                      <button
                        className="column-remove-btn"
                        draggable={false}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveColumn(header.key);
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
                      <div className="product-grid-header-label">
                        {header.label}
                        <span className="sort-indicator">
                          {isSorted && sortConfig?.direction === 'asc' && '↑'}
                          {isSorted && sortConfig?.direction === 'desc' && '↓'}
                          {isSorted && sorts.length > 1 && <span className="sort-order">{sortIndex + 1}</span>}
                        </span>
                      </div>
                      {header.unit && <div className="product-grid-header-unit">({header.unit})</div>}
                      <div
                        className="col-resize-handle"
                        draggable={false}
                        onMouseDown={(e) => {
                          e.stopPropagation();
                          startResize(header.key, e);
                        }}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                  );
                });
              })()}
              {/* Computed columns for Z-axis */}
              {appType === 'z-axis' && isLinearMode && loadMass > 0 && (
                <>
                  <div className="product-grid-header-item computed-col" style={{ width: 70 }}>
                    <div className="product-grid-header-label">Gravity</div>
                    <div className="product-grid-header-unit">(N)</div>
                  </div>
                  <div className="product-grid-header-item computed-col" style={{ width: 80 }}>
                    <div className="product-grid-header-label">Net Thrust</div>
                    <div className="product-grid-header-unit">(N)</div>
                  </div>
                  <div className="product-grid-header-item computed-col" style={{ width: 80 }}>
                    <div className="product-grid-header-label">Brake Hold</div>
                    <div className="product-grid-header-unit">(N)</div>
                  </div>
                </>
              )}
              {/* Restore-hidden-column button — only rendered when
                  there's something to restore. */}
              {hiddenColumnAttributes.length > 0 && (
                <button
                  ref={(el) => setAddColumnBtnRef(el)}
                  className="add-column-btn"
                  onClick={(e) => {
                    setColumnSelectorCursor({ x: e.clientX, y: e.clientY });
                    setShowSortSelector(true);
                  }}
                  title={`Add spec column (${hiddenColumnAttributes.length} available)`}
                >
                  + Add Spec
                </button>
              )}
            </div>

              {paginatedProducts.map((product) => (
                <div
                  key={product.product_id}
                  className="product-card-minimal"
                  onClick={(e) => handleProductClick(product, e)}
                >
                  {/* Product info - first grid cell. Part number is plain
                      text; clicking the row opens the detail modal, which
                      hosts the (intentionally singular) datasheet link. */}
                  <div className="product-card-info">
                    <div className="product-info-part">
                      {product.part_number || 'N/A'}
                    </div>
                  </div>

                  {/* Spec values - each as a direct grid cell */}
                  {getColumnHeaders().map((header) => {
                    const attrKey = header.key;
                    const productValue = (product as any)[attrKey];
                    const numericValue = extractNumericOnly(productValue);
                    const proximityColor = getProximityColor(attrKey, productValue);
                    const hasProximityColor = !!proximityColor;
                    const sortColor = !hasProximityColor
                      ? getSortGradientColor(attrKey, productValue)
                      : '';
                    const cellColor = proximityColor || sortColor || undefined;

                    return (
                      <div
                        key={`default-value-${attrKey}`}
                        className={`spec-header-item ${
                          !hasProximityColor && isFilteredAttribute(attrKey) ? 'spec-header-item-filtered' :
                          !hasProximityColor && isSortedAttribute(attrKey) ? 'spec-header-item-sorted' : ''
                        }`}
                        style={{
                          backgroundColor: cellColor
                        }}
                      >
                        <div className="spec-header-value">{numericValue || formatValue(productValue, 0, 5, unitSystem)}</div>
                      </div>
                    );
                  })}

                  {/* Z-axis computed values */}
                  {appType === 'z-axis' && isLinearMode && loadMass > 0 && (() => {
                    const gravityForce = parseFloat((loadMass * GRAVITY).toPrecision(4));
                    const ratedThrustVal = (product as any).rated_torque;
                    const thrustNum = ratedThrustVal && typeof ratedThrustVal === 'object' && 'value' in ratedThrustVal
                      ? ratedThrustVal.value : null;
                    const netThrust = thrustNum !== null ? parseFloat((thrustNum - gravityForce).toPrecision(4)) : null;
                    return (
                      <>
                        <div className="spec-header-item computed-cell">
                          <div className="spec-header-value">{gravityForce.toFixed(1)}</div>
                        </div>
                        <div className={`spec-header-item computed-cell ${netThrust !== null && netThrust < 0 ? 'computed-cell-warning' : ''}`}>
                          <div className="spec-header-value">{netThrust !== null ? netThrust.toFixed(1) : '-'}</div>
                        </div>
                        <div className="spec-header-item computed-cell">
                          <div className="spec-header-value">{gravityForce.toFixed(1)}</div>
                        </div>
                      </>
                    );
                  })()}

                </div>
              ))}
            </div>
            </div>

            {/* Pagination navigation */}
            {totalPages > 1 && (
              <div className="pagination-nav">
                <button
                  className="pagination-btn"
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                >
                  ← Previous
                </button>
                <span className="pagination-info">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  className="pagination-btn"
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </main>

      {/* Right sidebar - filters & gear ratio */}
      <aside className="filter-sidebar">
        {/* Mobile-only toggle header. Collapsed by default — phones don't
         * have the vertical real estate to host the full pane above the
         * results table. The summary line tells the user what the current
         * scope is (product type) and how many specs are pinned, so they
         * can decide whether to expand without doing it first. */}
        <button
          className="mobile-filter-toggle"
          onClick={() => setMobileFiltersOpen(prev => !prev)}
          aria-expanded={mobileFiltersOpen}
          aria-label={mobileFiltersOpen ? 'Hide filters' : 'Show filters'}
        >
          <span className="mobile-filter-summary">
            <span className="mobile-filter-prefix">Filters</span>
            <span className="mobile-filter-scope">
              {productType
                ? categories.find(c => c.type === productType)?.display_name ?? productType
                : 'Pick a type'}
            </span>
            {filters.length > 0 && (
              <span
                className="mobile-filter-count"
                aria-label={`${filters.length} active spec filter${filters.length === 1 ? '' : 's'}`}
              >
                {filters.length}
              </span>
            )}
          </span>
          <span className={`mobile-filter-arrow ${mobileFiltersOpen ? 'open' : ''}`} aria-hidden="true">&#9662;</span>
        </button>

        <div className={`filter-sidebar-body${mobileFiltersOpen ? ' mobile-expanded' : ''}`}>
        {productType === 'motor' && (
          <div className="transmission-control">
            {/* Application type selector */}
            <div className="transmission-type-row">
              {(['rotary', 'linear', 'z-axis'] as const).map(t => (
                <button
                  key={t}
                  className={`transmission-type-btn ${appType === t ? 'transmission-type-active' : ''}`}
                  onClick={() => {
                    setAppType(t);
                    if (t === 'rotary') { setLinearTravel(0); setLoadMass(0); }
                    if (t === 'linear') setLoadMass(0);
                  }}
                >
                  {t === 'z-axis' ? 'Z-Axis' : t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {/* Linear Travel / Rev — shown for linear and z-axis */}
            {(appType === 'linear' || appType === 'z-axis') && (
              <div className="transmission-param">
                <label className="transmission-param-label">Linear Travel / Rev</label>
                <div className="transmission-param-input-row">
                  <input
                    type="number"
                    className="transmission-param-input"
                    min={0}
                    step={0.1}
                    value={linearTravel || ''}
                    placeholder="0"
                    onChange={(e) => setLinearTravel(Math.max(0, Number(e.target.value) || 0))}
                  />
                  <span className="transmission-param-unit">mm/rev</span>
                </div>
                {linearTravel > 0 && (
                  <div className="transmission-param-hint">
                    RPM → mm/s, Torque → Thrust (N)
                  </div>
                )}
              </div>
            )}

            {/* Load Mass — shown for z-axis */}
            {appType === 'z-axis' && (
              <div className="transmission-param">
                <label className="transmission-param-label">Load Mass</label>
                <div className="transmission-param-input-row">
                  <input
                    type="number"
                    className="transmission-param-input"
                    min={0}
                    step={0.1}
                    value={loadMass || ''}
                    placeholder="0"
                    onChange={(e) => setLoadMass(Math.max(0, Number(e.target.value) || 0))}
                  />
                  <span className="transmission-param-unit">kg</span>
                </div>
                {loadMass > 0 && (
                  <div className="transmission-param-hint">
                    Gravity: {(loadMass * GRAVITY).toFixed(1)} N — Brake must hold this
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        <FilterBar
          productType={productType}
          filters={filters}
          sort={null}
          products={filteredProducts}
          onFiltersChange={setFilters}
          onSortChange={() => {}}
          onProductTypeChange={handleProductTypeChange}
          allProducts={linearizedSource}
        />
        </div>
      </aside>

      <ProductDetailModal
        product={selectedProduct}
        onClose={handleCloseModal}
        clickPosition={clickPosition}
      />

      {/* Attribute Selector Modal — shows currently-hidden columns so
          the user can restore them. Passes hiddenColumnAttributes (not
          the full list) so only hideable items appear. */}
      <AttributeSelector
        attributes={hiddenColumnAttributes}
        onSelect={handleAddColumn}
        onClose={() => {
          setShowSortSelector(false);
          setColumnSelectorCursor(null);
        }}
        isOpen={showSortSelector}
        anchorElement={addColumnBtnRef}
        cursorPosition={columnSelectorCursor}
      />
    </div>
  );
}
