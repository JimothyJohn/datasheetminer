/**
 * Product list component with advanced filtering and sorting
 */

import { useState, useEffect, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { ProductType, Product } from '../types/models';
import { FilterCriterion, SortConfig, applyFilters, sortProducts, getAttributesForType, deriveAttributesFromRecords, mergeAttributesByKey, AttributeMetadata } from '../types/filters';
import { formatValue } from '../utils/formatting';
import { extractNumeric, numericFromValue } from '../utils/filterValues';
import { useColumnResize } from '../utils/hooks';
import FilterBar from './FilterBar';
import ProductDetailModal from './ProductDetailModal';
import AttributeSelector from './AttributeSelector';

export default function ProductList() {
  const { products, categories, loading, error, loadProducts, loadCategories } = useApp();
  const [productType, setProductType] = useState<ProductType>(null);
  const [filters, setFilters] = useState<FilterCriterion[]>([]);
  const [sorts, setSorts] = useState<SortConfig[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [clickPosition, setClickPosition] = useState<{ x: number; y: number } | null>(null);
  const [showSortSelector, setShowSortSelector] = useState(false);
  const [itemsPerPage, setItemsPerPage] = useState<number>(25);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [additionalColumns, setAdditionalColumns] = useState<string[]>([]);
  const [addColumnBtnRef, setAddColumnBtnRef] = useState<HTMLButtonElement | null>(null);
  const [gearRatio, setGearRatio] = useState<number>(1);
  const [autoGear, setAutoGear] = useState<boolean>(true);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [appType, setAppType] = useState<'rotary' | 'linear' | 'z-axis'>('rotary');
  const [linearTravel, setLinearTravel] = useState<number>(0); // mm/rev
  const [screwEfficiency, setScrewEfficiency] = useState<number>(90); // % (ball screw ~90, lead screw ~30-50)
  const [loadMass, setLoadMass] = useState<number>(0); // kg (for Z-axis gravity calc)

  // Row-height preference. Persisted across sessions so user doesn't
  // have to re-toggle on every page load. 'compact' matches the
  // historical density; 'comfy' bumps vertical padding for readability.
  const [rowDensity, setRowDensity] = useState<'compact' | 'comfy'>(() => {
    if (typeof window === 'undefined') return 'compact';
    const stored = window.localStorage.getItem('productListRowDensity');
    return stored === 'comfy' ? 'comfy' : 'compact';
  });
  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem('productListRowDensity', rowDensity);
  }, [rowDensity]);

  // Default column widths (px): part number + spec columns
  const defaultPartWidth = 120;
  const defaultColWidth = 90;
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

  // Full ordered column list: merge curated per-type AttributeMetadata
  // (rich display names + tuned units) with attributes derived from the
  // actual records (catches schema evolution). Sorted alphabetically by
  // display name; exclusions applied. Single source of truth for both
  // header rendering and the column-width effect.
  const columnAttributes = useMemo<AttributeMetadata[]>(() => {
    if (!productType) return [];
    const staticAttrs = getAttributesForType(productType);
    const derivedAttrs = deriveAttributesFromRecords(products, productType);
    return mergeAttributesByKey(staticAttrs, derivedAttrs)
      .filter(a => !COLUMN_EXCLUDED_KEYS.has(a.key))
      .sort((a, b) => a.displayName.localeCompare(b.displayName));
  }, [productType, products, COLUMN_EXCLUDED_KEYS]);

  // Sync column widths when the column set changes.
  useEffect(() => {
    if (!productType) return;
    const defaults = columnAttributes.map(a => a.key);
    const allKeys = ['part_number', ...defaults, ...additionalColumns];
    setColumnWidths(prev => {
      const next: Record<string, number> = {};
      for (const key of allKeys) {
        next[key] = prev[key] ?? (key === 'part_number' ? defaultPartWidth : defaultColWidth);
      }
      return next;
    });
  }, [productType, additionalColumns, columnAttributes]);

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

  // Handle product type change
  const handleProductTypeChange = (newType: ProductType) => {
    setProductType(newType);
    setFilters([]);
    setSorts([]);
    setGearRatio(1);
    setAppType('rotary');
    setLinearTravel(0);
    setScrewEfficiency(90);
    setLoadMass(0);
  };

  // Gear ratio keys — torque is multiplied, speed is divided at the output
  const TORQUE_KEYS = ['rated_torque', 'peak_torque'];
  const SPEED_KEYS = ['rated_speed'];

  // Transform filters so user-entered values represent the geared output (manual mode only).
  const gearedFilters = useMemo(() => {
    if (gearRatio === 1 || productType !== 'motor') return filters;
    return filters.map(f => {
      if (f.value === undefined || typeof f.value !== 'number') return f;
      const baseAttr = f.attribute.split('.')[0];
      if (TORQUE_KEYS.includes(baseAttr)) {
        return { ...f, value: f.value / gearRatio };
      }
      if (SPEED_KEYS.includes(baseAttr)) {
        return { ...f, value: f.value * gearRatio };
      }
      return f;
    });
  }, [filters, gearRatio, productType]);

  const applyGearRatio = (value: any, ratio: number, multiply: boolean): any => {
    if (!value || ratio === 1) return value;
    const factor = multiply ? ratio : 1 / ratio;
    if (typeof value === 'object' && 'value' in value && typeof value.value === 'number') {
      return { ...value, value: parseFloat((value.value * factor).toPrecision(4)) };
    }
    if (typeof value === 'object' && 'min' in value && 'max' in value) {
      return {
        ...value,
        min: value.min != null ? parseFloat((value.min * factor).toPrecision(4)) : value.min,
        max: value.max != null ? parseFloat((value.max * factor).toPrecision(4)) : value.max,
      };
    }
    return value;
  };

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

  // --- Auto-gear: compute per-motor optimal gear ratio ---
  // For each motor, computes the minimum gear ratio that satisfies all torque/speed constraints.
  // Torque at output = motor_torque * R, Speed at output = motor_speed / R.
  const autoGearResults = useMemo(() => {
    if (!autoGear || productType !== 'motor') return null;

    // Split filters into gear-affected vs everything else
    const gearFilters: FilterCriterion[] = [];
    const otherFilters: FilterCriterion[] = [];
    for (const f of filters) {
      const base = f.attribute.split('.')[0];
      if ((TORQUE_KEYS.includes(base) || SPEED_KEYS.includes(base)) && f.mode === 'include' && typeof f.value === 'number') {
        gearFilters.push(f);
      } else {
        otherFilters.push(f);
      }
    }

    if (gearFilters.length === 0) return null;

    // Separate = and != filters — checked post-ratio-computation
    const boundFilters = gearFilters.filter(f => f.operator !== '=' && f.operator !== '!=');
    const postCheckFilters = gearFilters.filter(f => f.operator === '=' || f.operator === '!=');

    const candidates = applyFilters(products, otherFilters);
    const results: Array<Product & { _computedGearRatio: number }> = [];

    for (const product of candidates) {
      let rMin = 1;
      let rMax = Infinity;
      let feasible = true;

      for (const f of boundFilters) {
        const base = f.attribute.split('.')[0];
        const raw = extractNumeric(product, f.attribute);
        if (raw == null || raw === 0) { feasible = false; break; }

        const target = f.value as number;
        const isTorque = TORQUE_KEYS.includes(base);

        if (isTorque) {
          if (f.operator === '>=' || f.operator === '>') rMin = Math.max(rMin, target / raw);
          if (f.operator === '<=' || f.operator === '<') rMax = Math.min(rMax, target / raw);
        } else {
          if (f.operator === '>=' || f.operator === '>') rMax = Math.min(rMax, raw / target);
          if (f.operator === '<=' || f.operator === '<') rMin = Math.max(rMin, raw / target);
        }
      }

      // '=' pins R exactly
      for (const f of postCheckFilters) {
        if (f.operator !== '=') continue;
        const base = f.attribute.split('.')[0];
        const raw = extractNumeric(product, f.attribute);
        if (raw == null || raw === 0) { feasible = false; break; }
        const target = f.value as number;
        const pinned = TORQUE_KEYS.includes(base) ? target / raw : raw / target;
        rMin = Math.max(rMin, pinned);
        rMax = Math.min(rMax, pinned);
      }

      if (!feasible || rMin > rMax) continue;

      const ratio = Math.max(1, parseFloat(rMin.toPrecision(4)));
      if (ratio > rMax) continue;

      // '!=' post-check
      let excluded = false;
      for (const f of postCheckFilters) {
        if (f.operator !== '!=') continue;
        const base = f.attribute.split('.')[0];
        const raw = extractNumeric(product, f.attribute);
        if (raw == null) continue;
        const geared = TORQUE_KEYS.includes(base) ? raw * ratio : raw / ratio;
        if (geared === (f.value as number)) { excluded = true; break; }
      }
      if (excluded) continue;

      results.push({ ...product, _computedGearRatio: ratio } as Product & { _computedGearRatio: number });
    }

    return results;
  }, [products, filters, autoGear, productType]);

  const autoGearActive = autoGearResults !== null;

  // Summary stats for computed ratios (displayed in sidebar)
  const autoGearSummary = useMemo(() => {
    if (!autoGearResults || autoGearResults.length === 0) return null;
    const ratios = autoGearResults.map(r => r._computedGearRatio).sort((a, b) => a - b);
    return {
      min: ratios[0],
      max: ratios[ratios.length - 1],
      median: ratios[Math.floor(ratios.length / 2)],
      count: ratios.length,
    };
  }, [autoGearResults]);

  // Auto-gear path: filtering done inside autoGearResults.
  // Manual path: use gearedFilters (values transformed by global ratio).
  const filteredProducts = useMemo(() => {
    if (autoGearActive) {
      return autoGearResults! as Product[];
    }
    return applyFilters(products, gearedFilters);
  }, [products, gearedFilters, autoGearActive, autoGearResults]);

  // Get available attributes for sorting based on product type
  const availableAttributes = useMemo(() => {
    return getAttributesForType(productType);
  }, [productType]);

  // Apply sorting to filtered products
  const sortedProducts = useMemo(
    () => sortProducts(filteredProducts, sorts.length > 0 ? sorts : null),
    [filteredProducts, sorts]
  );

  // Transform display values: gear ratio + linear conversion if applicable
  const gearedProducts = useMemo(() => {
    const applyLinearConversions = (copy: any) => {
      if (!isLinearMode) return;
      for (const key of SPEED_KEYS) {
        if (copy[key]) copy[key] = rpmToLinearSpeed(copy[key]);
      }
      for (const key of TORQUE_KEYS) {
        if (copy[key]) copy[key] = torqueToThrust(copy[key]);
      }
    };

    if (autoGearActive) {
      return sortedProducts.map(p => {
        const ratio = (p as any)._computedGearRatio ?? 1;
        const copy = { ...p } as any;
        if (ratio !== 1) {
          for (const key of TORQUE_KEYS) {
            if (copy[key]) copy[key] = applyGearRatio(copy[key], ratio, true);
          }
          for (const key of SPEED_KEYS) {
            if (copy[key]) copy[key] = applyGearRatio(copy[key], ratio, false);
          }
        }
        applyLinearConversions(copy);
        return copy as Product;
      });
    }
    const needsGear = gearRatio !== 1 && productType === 'motor';
    if (!needsGear && !isLinearMode) return sortedProducts;
    return sortedProducts.map(p => {
      const copy = { ...p } as any;
      if (needsGear) {
        for (const key of TORQUE_KEYS) {
          if (copy[key]) copy[key] = applyGearRatio(copy[key], gearRatio, true);
        }
        for (const key of SPEED_KEYS) {
          if (copy[key]) copy[key] = applyGearRatio(copy[key], gearRatio, false);
        }
      }
      applyLinearConversions(copy);
      return copy as Product;
    });
  }, [sortedProducts, gearRatio, productType, autoGearActive, isLinearMode, linearTravel, screwEfficiency]);

  // Paginate products
  const paginatedProducts = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return gearedProducts.slice(startIndex, endIndex);
  }, [gearedProducts, currentPage, itemsPerPage]);

  const totalPages = Math.ceil(gearedProducts.length / itemsPerPage);

  // Reset to page 1 when filters, sorts, or items per page change
  useEffect(() => {
    setCurrentPage(1);
  }, [filters, sorts, itemsPerPage]);

  // Back-compat shim: existing call sites pass `productType` but the
  // computation is now state-driven via the `columnAttributes` memo
  // defined near the top of the component. Signature kept so surrounding
  // code doesn't need to change.
  const getDisplayedAttributes = (_productType: string): string[] =>
    columnAttributes.map(a => a.key);

  // Column headers with linear-mode label/unit overrides for SPEED_KEYS
  // and TORQUE_KEYS (thrust/force view for linear actuators).
  const getColumnHeaders = (): Array<{ key: string; label: string; unit: string | null }> => {
    return columnAttributes.map(attr => {
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
      return { key: attr.key, label, unit };
    });
  };

  // Extract just the numeric value from a spec (no unit)
  const extractNumericOnly = (value: any): string | null => {
    if (!value) return null;

    if (typeof value === 'number') return String(value);
    if (typeof value === 'string') return value;

    if (typeof value === 'object') {
      if ('value' in value && value.value !== null && value.value !== undefined) {
        return String(value.value);
      }

      const hasMin = 'min' in value && value.min !== null && value.min !== undefined;
      const hasMax = 'max' in value && value.max !== null && value.max !== undefined;

      if (hasMin && hasMax) {
        return `${value.min}-${value.max}`;
      } else if (hasMin) {
        return String(value.min);
      } else if (hasMax) {
        return String(value.max);
      }
    }

    return null;
  };

  // Extract just the unit from a spec
  const extractUnit = (value: any): string | null => {
    if (!value) return null;
    if (typeof value === 'object' && 'unit' in value) {
      return value.unit;
    }
    return null;
  };

  // Get color based on proximity to filter value
  const getProximityColor = (attribute: string, productValue: any): string => {
    const filter = filters.find(f => f.attribute === attribute || f.attribute.startsWith(attribute + '.'));
    if (!filter || filter.operator === '!=') return '';

    let numericProductValue: number | null = null;

    if (filter.attribute === attribute) {
      numericProductValue = numericFromValue(productValue);
    } else if (filter.attribute.startsWith(attribute + '.')) {
      const nestedKey = filter.attribute.split('.').pop();
      if (nestedKey && productValue && typeof productValue === 'object' && nestedKey in productValue) {
        numericProductValue = numericFromValue(productValue[nestedKey]);
      }
    }

    const numericFilterValue = numericFromValue(filter.value);

    if (numericProductValue === null || numericFilterValue === null) return '';
    if (numericFilterValue === 0) return '';

    if (filter.operator === '=') {
      const percentDiff = Math.abs((numericProductValue - numericFilterValue) / numericFilterValue) * 100;
      if (percentDiff === 0) return 'hsla(140, 40%, 50%, 0.25)';
      if (percentDiff < 5) return 'hsla(140, 30%, 50%, 0.2)';
      if (percentDiff < 10) return 'hsla(100, 30%, 50%, 0.2)';
      if (percentDiff < 20) return 'hsla(60, 30%, 50%, 0.2)';
      return '';
    }

    if (filter.operator === '>') {
      if (numericProductValue > numericFilterValue) {
        const percentOver = ((numericProductValue - numericFilterValue) / numericFilterValue) * 100;
        if (percentOver > 50) return 'hsla(140, 40%, 50%, 0.25)';
        if (percentOver > 25) return 'hsla(140, 30%, 50%, 0.2)';
        return 'hsla(100, 30%, 50%, 0.2)';
      }
    }

    if (filter.operator === '<') {
      if (numericProductValue < numericFilterValue) {
        const percentUnder = ((numericFilterValue - numericProductValue) / numericFilterValue) * 100;
        if (percentUnder > 50) return 'hsla(140, 40%, 50%, 0.25)';
        if (percentUnder > 25) return 'hsla(140, 30%, 50%, 0.2)';
        return 'hsla(100, 30%, 50%, 0.2)';
      }
    }

    return '';
  };

  const isSortedAttribute = (attribute: string): boolean => {
    return sorts.some(sort => sort.attribute === attribute);
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
    } else {
      const attributes = getAttributesForType(productType || 'motor');
      const attributeMetadata = attributes.find(attr => attr.key === attribute);
      if (attributeMetadata) {
        setSorts([...sorts, {
          attribute: attribute,
          direction: 'asc',
          displayName: attributeMetadata.displayName
        }]);
      }
    }
  };

  const handleRemoveColumn = (attribute: string, isDefault: boolean) => {
    setSorts(sorts.filter(s => s.attribute !== attribute));
    if (!isDefault) {
      setAdditionalColumns(additionalColumns.filter(col => col !== attribute));
    }
  };

  const handleAddColumn = (attribute: ReturnType<typeof getAttributesForType>[0]) => {
    const defaultColumns = getDisplayedAttributes(productType || '');
    if (!defaultColumns.includes(attribute.key) && !additionalColumns.includes(attribute.key)) {
      setAdditionalColumns([...additionalColumns, attribute.key]);
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
              <select
                className="pagination-select"
                value={itemsPerPage}
                onChange={(e) => setItemsPerPage(Number(e.target.value))}
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={250}>250</option>
                <option value={500}>500</option>
              </select>
            </div>
            <span className="results-count" style={{ marginLeft: '1rem' }}>
              {gearedProducts.length === 0 ? '0' : `${(currentPage - 1) * itemsPerPage + 1}-${Math.min(currentPage * itemsPerPage, gearedProducts.length)}`} of {gearedProducts.length}
            </span>
          </div>

          <div className="results-header-right">
            <button
              type="button"
              className="density-toggle-btn"
              onClick={() => setRowDensity(d => (d === 'compact' ? 'comfy' : 'compact'))}
              title={rowDensity === 'compact' ? 'Switch to comfortable row height' : 'Switch to compact row height'}
            >
              {rowDensity === 'compact' ? '☰ Compact' : '≡ Comfy'}
            </button>
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

        {productType === null || (!loading && gearedProducts.length === 0) ? (
          <div className="empty-state-minimal">
            <p>
              {productType === null
                ? 'Select a product type to begin'
                : products.length === 0
                ? 'No products in database'
                : 'No results match your filters'}
            </p>
          </div>
        ) : (
          <>
            <div className="product-grid-scroll">
            <div className={`product-grid density-${rowDensity}`}>
            {/* Column headers */}
            <div className="product-grid-headers">
              <div
                className="product-grid-header-part clickable"
                style={{ width: columnWidths['part_number'] ?? defaultPartWidth }}
                onClick={() => handleColumnSort('part_number')}
                title="Click to sort by Part Number"
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
              {/* Auto-gear ratio column */}
              {autoGearActive && (
                <div
                  className="product-grid-header-item gear-ratio-col"
                  style={{ width: 60 }}
                  title="Computed gear ratio needed to meet torque/speed filters"
                >
                  <div className="product-grid-header-label">Ratio</div>
                  <div className="product-grid-header-unit">(: 1)</div>
                </div>
              )}
              {/* Default columns */}
              {getColumnHeaders().map((header) => {
                const sortIndex = sorts.findIndex(s => s.attribute === header.key);
                const isSorted = sortIndex !== -1;
                const sortConfig = isSorted ? sorts[sortIndex] : null;

                return (
                  <div
                    key={header.key}
                    className="product-grid-header-item clickable"
                    style={{ width: columnWidths[header.key] ?? defaultColWidth }}
                    onClick={() => handleColumnSort(header.key)}
                    title="Click to sort"
                  >
                    <div className="product-grid-header-label">
                      {header.label}
                      <span className="sort-indicator">
                        {isSorted && sortConfig?.direction === 'asc' && '↑'}
                        {isSorted && sortConfig?.direction === 'desc' && '↓'}
                        {isSorted && sorts.length > 1 && <span className="sort-order">{sortIndex + 1}</span>}
                      </span>
                    </div>
                    {header.unit && <div className="product-grid-header-unit">({header.unit})</div>}
                    <div className="col-resize-handle" onMouseDown={(e) => startResize(header.key, e)} />
                  </div>
                );
              })}
              {/* Additional columns */}
              {additionalColumns.map((attrKey) => {
                const attributes = getAttributesForType(productType || 'motor');
                const attrMetadata = attributes.find(a => a.key === attrKey);
                if (!attrMetadata) return null;

                const firstProduct = gearedProducts[0];
                const unit = firstProduct ? extractUnit((firstProduct as any)[attrKey]) : null;

                const sortIndex = sorts.findIndex(s => s.attribute === attrKey);
                const isSorted = sortIndex !== -1;
                const sortConfig = isSorted ? sorts[sortIndex] : null;

                return (
                  <div
                    key={`additional-${attrKey}`}
                    className="product-grid-header-item clickable removable"
                    style={{ width: columnWidths[attrKey] ?? defaultColWidth }}
                  >
                    <button
                      className="column-remove-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveColumn(attrKey, false);
                      }}
                      title="Remove column"
                    >
                      ×
                    </button>
                    <div
                      className="product-grid-header-label"
                      onClick={() => handleColumnSort(attrKey)}
                      title="Click to sort"
                    >
                      {attrMetadata.displayName}
                      <span className="sort-indicator">
                        {isSorted && sortConfig?.direction === 'asc' && '↑'}
                        {isSorted && sortConfig?.direction === 'desc' && '↓'}
                        {isSorted && sorts.length > 1 && <span className="sort-order">{sortIndex + 1}</span>}
                      </span>
                    </div>
                    {unit && <div className="product-grid-header-unit">({unit})</div>}
                    <div className="col-resize-handle" onMouseDown={(e) => startResize(attrKey, e)} />
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
              {/* Computed inertia column for rotary */}
              {appType === 'rotary' && productType === 'motor' && (autoGearActive || gearRatio > 1) && (
                <div className="product-grid-header-item computed-col" style={{ width: 90 }}>
                  <div className="product-grid-header-label">Refl. Inertia</div>
                  <div className="product-grid-header-unit">(kg·cm²)</div>
                </div>
              )}
              {/* Add spec button */}
              <button
                ref={(el) => setAddColumnBtnRef(el)}
                className="add-column-btn"
                onClick={() => setShowSortSelector(true)}
                title="Add spec"
              >
                + Add Spec
              </button>
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

                  {/* Auto-gear ratio value */}
                  {autoGearActive && (
                    <div className="spec-header-item gear-ratio-cell">
                      <div className="spec-header-value">
                        {((product as any)._computedGearRatio ?? 1) <= 1.01 ? '1' : ((product as any)._computedGearRatio).toFixed(1)}
                      </div>
                    </div>
                  )}

                  {/* Spec values - each as a direct grid cell */}
                  {getColumnHeaders().map((header) => {
                    const attrKey = header.key;
                    const productValue = (product as any)[attrKey];
                    const numericValue = extractNumericOnly(productValue);
                    const proximityColor = getProximityColor(attrKey, productValue);
                    const hasProximityColor = !!proximityColor;

                    return (
                      <div
                        key={`default-value-${attrKey}`}
                        className={`spec-header-item ${
                          !hasProximityColor && isFilteredAttribute(attrKey) ? 'spec-header-item-filtered' :
                          !hasProximityColor && isSortedAttribute(attrKey) ? 'spec-header-item-sorted' : ''
                        }`}
                        style={{
                          backgroundColor: proximityColor || undefined
                        }}
                      >
                        <div className="spec-header-value">{numericValue || formatValue(productValue)}</div>
                      </div>
                    );
                  })}

                  {/* Show additional columns */}
                  {additionalColumns.map((attrKey) => {
                    const productValue = (product as any)[attrKey];
                    const numericValue = extractNumericOnly(productValue);
                    const proximityColor = getProximityColor(attrKey, productValue);
                    const hasProximityColor = !!proximityColor;
                    return (
                      <div
                        key={`additional-value-${attrKey}`}
                        className={`spec-header-item ${
                          !hasProximityColor && isFilteredAttribute(attrKey) ? 'spec-header-item-filtered' :
                          !hasProximityColor && isSortedAttribute(attrKey) ? 'spec-header-item-sorted' : ''
                        }`}
                        style={{
                          backgroundColor: proximityColor || undefined
                        }}
                      >
                        <div className="spec-header-value">{numericValue || formatValue(productValue)}</div>
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

                  {/* Rotary reflected inertia */}
                  {appType === 'rotary' && productType === 'motor' && (autoGearActive || gearRatio > 1) && (() => {
                    const ratio = autoGearActive ? ((product as any)._computedGearRatio ?? gearRatio) : gearRatio;
                    const rotorInertia = (product as any).rotor_inertia;
                    const inertiaVal = rotorInertia && typeof rotorInertia === 'object' && 'value' in rotorInertia
                      ? rotorInertia.value : null;
                    // Reflected inertia at output = J_motor * ratio²
                    const reflected = inertiaVal !== null ? parseFloat((inertiaVal * ratio * ratio).toPrecision(4)) : null;
                    return (
                      <div className="spec-header-item computed-cell">
                        <div className="spec-header-value">{reflected !== null ? reflected.toFixed(2) : '-'}</div>
                      </div>
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
          <div className="gear-ratio-control">
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

            {/* Gear ratio header */}
            <div className="gear-ratio-header">
              <span className="gear-ratio-icon">⚙</span>
              <span className="gear-ratio-label">Gear Ratio</span>
              <button
                className={`gear-auto-toggle ${autoGear ? 'gear-auto-active' : ''}`}
                onClick={() => {
                  setAutoGear(prev => !prev);
                  if (!autoGear) setGearRatio(1);
                }}
                title={autoGear ? 'Auto mode: per-motor ratio computed from filters' : 'Manual mode: fixed ratio for all motors'}
              >
                {autoGear ? 'Auto' : 'Manual'}
              </button>
            </div>
            {!autoGear && (
              <>
                <div className="gear-ratio-input-row">
                  <button
                    className="gear-ratio-step"
                    onClick={() => setGearRatio(r => Math.max(1, r - 5))}
                    disabled={gearRatio <= 1}
                  >
                    −
                  </button>
                  <div className="gear-ratio-display">
                    <input
                      type="number"
                      className="gear-ratio-input"
                      min={1}
                      max={100}
                      step={1}
                      value={gearRatio}
                      onChange={(e) => {
                        const v = Math.max(1, Math.min(100, Math.round(Number(e.target.value) || 1)));
                        setGearRatio(v);
                      }}
                    />
                    <span className="gear-ratio-suffix">: 1</span>
                  </div>
                  <button
                    className="gear-ratio-step"
                    onClick={() => setGearRatio(r => Math.min(100, r + 5))}
                    disabled={gearRatio >= 100}
                  >
                    +
                  </button>
                </div>
                {gearRatio > 1 && (
                  <button
                    className="gear-ratio-reset"
                    onClick={() => setGearRatio(1)}
                  >
                    Reset to direct drive
                  </button>
                )}
              </>
            )}
            {autoGear && autoGearActive && autoGearSummary && (
              <div className="gear-auto-summary">
                <div className="gear-auto-range">
                  {autoGearSummary.min === autoGearSummary.max ? (
                    <span className="gear-auto-value">{autoGearSummary.min <= 1.01 ? '1' : autoGearSummary.min.toFixed(1)}:1</span>
                  ) : (
                    <>
                      <span className="gear-auto-value">{autoGearSummary.min <= 1.01 ? '1' : autoGearSummary.min.toFixed(1)}</span>
                      <span className="gear-auto-sep"> - </span>
                      <span className="gear-auto-value">{autoGearSummary.max.toFixed(1)}</span>
                      <span className="gear-auto-unit">: 1</span>
                    </>
                  )}
                </div>
                <div className="gear-auto-detail">
                  Median {autoGearSummary.median <= 1.01 ? '1' : autoGearSummary.median.toFixed(1)}:1 across {autoGearSummary.count} motors
                </div>
              </div>
            )}
            {autoGear && autoGearActive && !autoGearSummary && (
              <div className="gear-auto-hint">No motors match these constraints</div>
            )}
            {autoGear && !autoGearActive && (
              <div className="gear-auto-hint">
                Add a torque or speed filter to auto-compute ratios
              </div>
            )}

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

            {/* Rotary inertia info */}
            {appType === 'rotary' && (autoGearActive || gearRatio > 1) && (
              <div className="transmission-param-hint" style={{ marginTop: '0.4rem' }}>
                Reflected inertia at output = J_rotor × R²
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
          allProducts={products}
        />
        </div>
      </aside>

      <ProductDetailModal
        product={selectedProduct}
        onClose={handleCloseModal}
        clickPosition={clickPosition}
      />

      {/* Attribute Selector Modal for Adding Columns */}
      <AttributeSelector
        attributes={availableAttributes}
        onSelect={handleAddColumn}
        onClose={() => {
          setShowSortSelector(false);
        }}
        isOpen={showSortSelector}
        anchorElement={addColumnBtnRef}
      />
    </div>
  );
}
