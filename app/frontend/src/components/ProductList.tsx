/**
 * Product list component with advanced filtering and sorting
 */

import { useState, useEffect, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { ProductType, Product } from '../types/models';
import { FilterCriterion, SortConfig, applyFilters, sortProducts, getAttributesForType } from '../types/filters';
import { formatValue } from '../utils/formatting';
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

  // Default column widths (px): part number + spec columns
  const defaultPartWidth = 120;
  const defaultColWidth = 90;
  const { columnWidths, setColumnWidths, startResize } = useColumnResize({ part_number: defaultPartWidth });

  // Sync column widths when product type or additional columns change
  useEffect(() => {
    if (!productType) return;
    const defaults = getDisplayedAttributes(productType);
    const allKeys = ['part_number', ...defaults, ...additionalColumns];
    setColumnWidths(prev => {
      const next: Record<string, number> = {};
      for (const key of allKeys) {
        next[key] = prev[key] ?? (key === 'part_number' ? defaultPartWidth : defaultColWidth);
      }
      return next;
    });
  }, [productType, additionalColumns]);

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
  };

  // Gear ratio keys — torque is multiplied, speed is divided at the output
  const TORQUE_KEYS = ['rated_torque', 'peak_torque'];
  const SPEED_KEYS = ['rated_speed'];

  // Transform filters so user-entered values represent the geared output.
  // User says "torque >= 50 Nm" at 10:1 → raw motor needs torque >= 5 Nm.
  // User says "speed >= 300 rpm" at 10:1 → raw motor needs speed >= 3000 rpm.
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

  // Apply filters (with gear-adjusted values) to raw products
  const filteredProducts = useMemo(
    () => applyFilters(products, gearedFilters),
    [products, gearedFilters]
  );

  // Get available attributes for sorting based on product type
  const availableAttributes = useMemo(() => {
    return getAttributesForType(productType);
  }, [productType]);

  // Apply sorting to filtered products
  const sortedProducts = useMemo(
    () => sortProducts(filteredProducts, sorts.length > 0 ? sorts : null),
    [filteredProducts, sorts]
  );

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

  const gearedProducts = useMemo(() => {
    if (gearRatio === 1 || productType !== 'motor') return sortedProducts;
    return sortedProducts.map(p => {
      const copy = { ...p } as any;
      for (const key of TORQUE_KEYS) {
        if (copy[key]) copy[key] = applyGearRatio(copy[key], gearRatio, true);
      }
      for (const key of SPEED_KEYS) {
        if (copy[key]) copy[key] = applyGearRatio(copy[key], gearRatio, false);
      }
      return copy as Product;
    });
  }, [sortedProducts, gearRatio, productType]);

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

  // Get which attributes are displayed in the main specs for each product type
  const getDisplayedAttributes = (productType: string): string[] => {
    if (productType === 'motor') {
      return ['rated_power', 'rated_voltage', 'rated_current', 'rated_speed', 'rated_torque', 'peak_torque'];
    } else if (productType === 'drive') {
      return ['output_power', 'input_voltage', 'rated_current', 'peak_current', 'input_voltage_phases', 'ip_rating'];
    }
    return [];
  };

  // Get column header labels for the current product type with units from metadata
  const getColumnHeaders = (): Array<{ key: string; label: string; unit: string | null }> => {
    if (!productType) return [];

    const displayedKeys = getDisplayedAttributes(productType);
    const allAttributes = getAttributesForType(productType);

    return displayedKeys.map(key => {
      const attr = allAttributes.find(a => a.key === key);
      return {
        key: key,
        label: attr ? attr.displayName : key,
        unit: attr ? attr.unit || null : null
      };
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

  // Extract numeric value from a value object
  const extractNumericValue = (value: any): number | null => {
    if (!value) return null;
    if (typeof value === 'number') return value;
    if (typeof value === 'object') {
      if ('value' in value && typeof value.value === 'number') return value.value;
      if ('nominal' in value && typeof value.nominal === 'number') return value.nominal;
      if ('rated' in value && typeof value.rated === 'number') return value.rated;

      const hasMin = 'min' in value && value.min !== null && value.min !== undefined;
      const hasMax = 'max' in value && value.max !== null && value.max !== undefined;

      if (hasMin && hasMax) {
        return (Number(value.min) + Number(value.max)) / 2;
      } else if (hasMin) {
        return Number(value.min);
      } else if (hasMax) {
        return Number(value.max);
      }
    }
    return null;
  };

  // Get color based on proximity to filter value
  const getProximityColor = (attribute: string, productValue: any): string => {
    const filter = filters.find(f => f.attribute === attribute || f.attribute.startsWith(attribute + '.'));
    if (!filter || filter.operator === '!=') return '';

    let numericProductValue: number | null = null;

    if (filter.attribute === attribute) {
      numericProductValue = extractNumericValue(productValue);
    } else if (filter.attribute.startsWith(attribute + '.')) {
      const nestedKey = filter.attribute.split('.').pop();
      if (nestedKey && productValue && typeof productValue === 'object' && nestedKey in productValue) {
        numericProductValue = extractNumericValue(productValue[nestedKey]);
      }
    }

    const numericFilterValue = extractNumericValue(filter.value);

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
            {loading && (
              <span style={{ opacity: 0.6, fontSize: '0.8rem' }}>
                Loading...
              </span>
            )}
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
            <div className="product-grid">
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
                      {product.datasheet_url?.url ? (
                        <a
                          href={product.datasheet_url.url}
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
                </div>
              ))}
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
        {productType === 'motor' && (
          <div className="gear-ratio-control">
            <div className="gear-ratio-header">
              <span className="gear-ratio-icon">⚙</span>
              <span className="gear-ratio-label">Gear Ratio</span>
            </div>
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
