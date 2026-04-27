/**
 * Product list component with advanced filtering and sorting
 */

import { useState, useEffect, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { ProductType, Product } from '../types/models';
import { FilterCriterion, SortConfig, applyFilters, sortProducts, getAttributesForType, deriveAttributesFromRecords, mergeAttributesByKey, AttributeMetadata, getAvailableOperators } from '../types/filters';
// Column order is authored in types/columnOrder.ts — edit that file to
// change what columns appear and in what order.
import { orderColumnAttributes } from '../types/columnOrder';
import { formatValue } from '../utils/formatting';
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
import { getAttributeIcon } from '../utils/attributeIcons';

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

  // Hard cap on simultaneously visible spec columns. Compact rows fit ten
  // before the table feels crowded; comfy is six so the row breathes
  // without horizontal scrolling. Extras spill into the restore dropdown
  // and stay individually restorable.
  const MAX_VISIBLE_COLUMNS = rowDensity === 'compact' ? 10 : 6;
  const [addColumnBtnRef, setAddColumnBtnRef] = useState<HTMLButtonElement | null>(null);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [appType, setAppType] = useState<'rotary' | 'linear' | 'z-axis'>('rotary');
  const [linearTravel, setLinearTravel] = useState<number>(0); // mm/rev
  const [screwEfficiency, setScrewEfficiency] = useState<number>(90); // % (ball screw ~90, lead screw ~30-50)
  const [loadMass, setLoadMass] = useState<number>(0); // kg (for Z-axis gravity calc)

// Default column widths (px): part number + spec columns. Comfy mode
// widens both so the bumped font size has room to breathe; toggling
// density resets widths to that mode's defaults (see effect below).
  const defaultPartWidth = rowDensity === 'compact' ? 120 : 160;
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
    return shown.slice(0, MAX_VISIBLE_COLUMNS);
  }, [columnAttributes, userHiddenKeys, userRestoredKeys, MAX_VISIBLE_COLUMNS]);

  // Restore-dropdown candidates: everything the user could bring back —
  // explicit hides, cap overflow, and the hidden-by-default non-unit
  // kinds (strings, booleans, arrays, bare numbers).
  const hiddenColumnAttributes = useMemo<AttributeMetadata[]>(() => {
    const visibleKeys = new Set(visibleColumnAttributes.map(a => a.key));
    return columnAttributes.filter(a => !visibleKeys.has(a.key));
  }, [columnAttributes, visibleColumnAttributes]);

  // Sync column widths when the visible column set changes. When
  // `rowDensity` flips, we clobber instead of preserving so the new
  // defaults actually take effect — manual resizes within a mode are
  // still respected until the next density toggle.
  useEffect(() => {
    if (!productType) return;
    const defaults = visibleColumnAttributes.map(a => a.key);
    const allKeys = ['part_number', ...defaults];
    setColumnWidths(prev => {
      const next: Record<string, number> = {};
      for (const key of allKeys) {
        next[key] = prev[key] ?? (key === 'part_number' ? defaultPartWidth : defaultColWidth);
      }
      return next;
    });
  }, [productType, visibleColumnAttributes]);

  // Reset widths to the active density's defaults whenever density flips.
  useEffect(() => {
    setColumnWidths(prev => {
      const next: Record<string, number> = {};
      for (const key of Object.keys(prev)) {
        next[key] = key === 'part_number' ? defaultPartWidth : defaultColWidth;
      }
      return next;
    });
  }, [rowDensity, defaultPartWidth, defaultColWidth, setColumnWidths]);

  // Load products and categories when product type changes or on mount
  useEffect(() => {
    if (productType !== null) {
      loadProducts(productType);
    }
    if (categories.length === 0) {
      loadCategories();
    }
  }, [productType, loadProducts, loadCategories]);

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

  // Slider-operator → sort direction. The user's "seek method": picking
  // `>=` means they're hunting for high values (sort desc); picking `<`
  // means they want low values (sort asc). If a sort already exists for
  // this attribute (e.g. set via column-header click), flip its direction
  // in place to preserve any multi-level sort hierarchy. If no prior sort,
  // prepend so the seek direction takes the primary slot.
  const handleSortByOperator = (
    attribute: string,
    displayName: string,
    direction: 'asc' | 'desc',
  ) => {
    setSorts(prev => {
      const idx = prev.findIndex(s => s.attribute === attribute);
      if (idx !== -1) {
        const next = [...prev];
        next[idx] = { attribute, displayName, direction };
        return next;
      }
      return [{ attribute, displayName, direction }, ...prev];
    });
  };

  // Handle product type change
  const handleProductTypeChange = (newType: ProductType) => {
    setProductType(newType);
    setFilters([]);
    setSorts([]);
    setAppType('rotary');
    setLinearTravel(0);
    setScrewEfficiency(90);
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
  // F = T * 2π * η / lead   (lead in meters, η = efficiency 0-1)
  const torqueToThrust = (value: any): any => {
    if (!value || !linearTravel) return value;
    const eta = screwEfficiency / 100;
    const factor = (2 * Math.PI * eta) / (linearTravel * 0.001);
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

  const filteredProducts = useMemo(() => {
    return applyFilters(compatNarrowed, filters);
  }, [compatNarrowed, filters]);

  // Apply sorting to filtered products
  const sortedProducts = useMemo(
    () => sortProducts(filteredProducts, sorts.length > 0 ? sorts : null),
    [filteredProducts, sorts]
  );

  // Transform display values for linear / z-axis modes.
  const displayProducts = useMemo(() => {
    if (!isLinearMode) return sortedProducts;
    return sortedProducts.map(p => {
      const copy = { ...p } as any;
      for (const key of SPEED_KEYS) {
        if (copy[key]) copy[key] = rpmToLinearSpeed(copy[key]);
      }
      for (const key of TORQUE_KEYS) {
        if (copy[key]) copy[key] = torqueToThrust(copy[key]);
      }
      return copy as Product;
    });
  }, [sortedProducts, isLinearMode, linearTravel, screwEfficiency]);

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
              {getColumnHeaders().map((header) => {
                const sortIndex = sorts.findIndex(s => s.attribute === header.key);
                const isSorted = sortIndex !== -1;
                const sortConfig = isSorted ? sorts[sortIndex] : null;
                const Icon = getAttributeIcon(header.key);

                return (
                  <div
                    key={header.key}
                    className="product-grid-header-item clickable removable"
                    style={{ width: columnWidths[header.key] ?? defaultColWidth }}
                    title="Click anywhere to sort • click again to reverse, again to clear"
                    onClick={() => handleColumnSort(header.key)}
                  >
                    <button
                      className="column-remove-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveColumn(header.key);
                      }}
                      title="Hide column"
                    >
                      ×
                    </button>
                    {Icon && <Icon className="header-attr-icon" aria-hidden="true" />}
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
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        startResize(header.key, e);
                      }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </div>
                );
              })}
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
                  {/* Product info - first grid cell */}
                  <div className="product-card-info">
                    <div className="product-info-part">
                      {(typeof product.datasheet_url === 'string' ? product.datasheet_url : product.datasheet_url?.url) ? (
                        <a
                          href={typeof product.datasheet_url === 'string' ? product.datasheet_url : product.datasheet_url!.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          style={{ color: 'inherit', textDecoration: 'underline', textDecorationColor: 'var(--text-tertiary)', textUnderlineOffset: '2px' }}
                        >
                          {product.part_number || 'N/A'}
                        </a>
                      ) : (
                        product.part_number || 'N/A'
                      )}
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
        {/* Mobile-only toggle header */}
        <button
          className="mobile-filter-toggle"
          onClick={() => setMobileFiltersOpen(prev => !prev)}
        >
          <span className="mobile-filter-summary">
            {productType
              ? categories.find(c => c.type === productType)?.display_name ?? productType
              : 'Select Type'}
            {filters.length > 0 && (
              <span className="mobile-filter-count">{filters.length}</span>
            )}
          </span>
          <span className={`mobile-filter-arrow ${mobileFiltersOpen ? 'open' : ''}`}>&#9662;</span>
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

            {/* Screw efficiency — shown when linear travel is set */}
            {(appType === 'linear' || appType === 'z-axis') && linearTravel > 0 && (
              <div className="transmission-param">
                <label className="transmission-param-label">Screw Efficiency</label>
                <div className="transmission-param-input-row">
                  <input
                    type="range"
                    className="transmission-efficiency-slider"
                    min={10}
                    max={100}
                    step={1}
                    value={screwEfficiency}
                    onChange={(e) => setScrewEfficiency(Number(e.target.value))}
                  />
                  <span className="transmission-param-unit">{screwEfficiency}%</span>
                </div>
                <div className="transmission-param-hint">
                  Ball screw ~90%, Lead screw ~30-50%
                </div>
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
          onSortByOperator={handleSortByOperator}
          onProductTypeChange={handleProductTypeChange}
          allProducts={products}
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
