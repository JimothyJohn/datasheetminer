/**
 * Product list component with advanced filtering and sorting
 */

import { useState, useEffect, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { ProductType, Product } from '../types/models';
import { FilterCriterion, SortConfig, applyFilters, sortProducts, getAttributesForType } from '../types/filters';
import { formatValue } from '../utils/formatting';
import FilterBar from './FilterBar';
import ProductDetailModal from './ProductDetailModal';
import AttributeSelector from './AttributeSelector';

export default function ProductList() {
  const { products, categories, loading, error, loadProducts, loadCategories, forceRefresh } = useApp();
  const [productType, setProductType] = useState<ProductType>(null);
  const [filters, setFilters] = useState<FilterCriterion[]>([]);
  const [sorts, setSorts] = useState<SortConfig[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [clickPosition, setClickPosition] = useState<{ x: number; y: number } | null>(null);
  const [showSortSelector, setShowSortSelector] = useState(false);
  const [draggedSortIndex, setDraggedSortIndex] = useState<number | null>(null);
  const [itemsPerPage, setItemsPerPage] = useState<number>(25);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [additionalColumns, setAdditionalColumns] = useState<string[]>([]);

  // Load products and categories when product type changes or on mount
  useEffect(() => {
    // Only load products if a product type is selected
    if (productType !== null) {
      loadProducts(productType);
    }
    if (categories.length === 0) {
      loadCategories();
    }
  }, [productType]);

  // Add keyboard shortcut for opening filter (Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        // Trigger add filter button click
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
    // Reset filters and sorts when changing product type
    setFilters([]);
    setSorts([]);
  };

  // Apply filters first
  const filteredProducts = useMemo(
    () => applyFilters(products, filters),
    [products, filters]
  );

  // Get available attributes for sorting based on product type
  // Simply show all attributes for the selected product type
  const availableAttributes = useMemo(() => {
    return getAttributesForType(productType);
  }, [productType]);


  // Handle toggling sort direction
  const handleToggleSortDirection = (index: number) => {
    setSorts(prev => prev.map((sort, i) =>
      i === index ? { ...sort, direction: sort.direction === 'asc' ? 'desc' : 'asc' } : sort
    ));
  };

  // Drag and drop handlers
  const handleDragStart = (index: number) => {
    setDraggedSortIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedSortIndex === null || draggedSortIndex === index) return;

    const newSorts = [...sorts];
    const draggedItem = newSorts[draggedSortIndex];
    newSorts.splice(draggedSortIndex, 1);
    newSorts.splice(index, 0, draggedItem);

    setSorts(newSorts);
    setDraggedSortIndex(index);
  };

  const handleDragEnd = () => {
    setDraggedSortIndex(null);
  };

  // Apply sorting to filtered products
  const sortedProducts = useMemo(
    () => sortProducts(filteredProducts, sorts.length > 0 ? sorts : null),
    [filteredProducts, sorts]
  );

  // Paginate products
  const paginatedProducts = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return sortedProducts.slice(startIndex, endIndex);
  }, [sortedProducts, currentPage, itemsPerPage]);

  const totalPages = Math.ceil(sortedProducts.length / itemsPerPage);

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
      // ValueUnit: { value: number, unit: string }
      if ('value' in value && value.value !== null && value.value !== undefined) {
        return String(value.value);
      }

      // MinMaxUnit: { min: number, max: number, unit: string }
      // Handle cases where only one property might be present
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

    // ValueUnit or MinMaxUnit: { ..., unit: string }
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

      // Handle min/max - check which values are present
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
    // Find if there's a filter for this attribute (exact or nested property)
    const filter = filters.find(f => f.attribute === attribute || f.attribute.startsWith(attribute + '.'));
    if (!filter || filter.operator === '!=') return '';

    // Determine the actual value to compare
    let numericProductValue: number | null = null;

    if (filter.attribute === attribute) {
      // Direct attribute match
      numericProductValue = extractNumericValue(productValue);
    } else if (filter.attribute.startsWith(attribute + '.')) {
      // Nested property (e.g., filtering on 'input_voltage.min' when attribute is 'input_voltage')
      const nestedKey = filter.attribute.split('.').pop(); // Get 'min' or 'max'
      if (nestedKey && productValue && typeof productValue === 'object' && nestedKey in productValue) {
        numericProductValue = extractNumericValue(productValue[nestedKey]);
      }
    }

    const numericFilterValue = extractNumericValue(filter.value);

    if (numericProductValue === null || numericFilterValue === null) return '';

    // For equality filters, check if values match
    if (filter.operator === '=') {
      const percentDiff = Math.abs((numericProductValue - numericFilterValue) / numericFilterValue) * 100;
      if (percentDiff === 0) return 'hsl(140, 65%, 45%)'; // Perfect match - bright green
      if (percentDiff < 5) return 'hsl(140, 55%, 50%)';
      if (percentDiff < 10) return 'hsl(100, 50%, 45%)';
      if (percentDiff < 20) return 'hsl(60, 50%, 45%)';
      return '';
    }

    // For comparison filters (> or <), show green if condition is met
    if (filter.operator === '>') {
      if (numericProductValue > numericFilterValue) {
        const percentOver = ((numericProductValue - numericFilterValue) / numericFilterValue) * 100;
        if (percentOver > 50) return 'hsl(140, 65%, 45%)';
        if (percentOver > 25) return 'hsl(140, 55%, 50%)';
        return 'hsl(100, 50%, 45%)';
      }
    }

    if (filter.operator === '<') {
      if (numericProductValue < numericFilterValue) {
        const percentUnder = ((numericFilterValue - numericProductValue) / numericFilterValue) * 100;
        if (percentUnder > 50) return 'hsl(140, 65%, 45%)';
        if (percentUnder > 25) return 'hsl(140, 55%, 50%)';
        return 'hsl(100, 50%, 45%)';
      }
    }

    return '';
  };

  // Check if an attribute is currently being sorted
  const isSortedAttribute = (attribute: string): boolean => {
    return sorts.some(sort => sort.attribute === attribute);
  };

  // Check if an attribute is currently being filtered (including nested properties)
  const isFilteredAttribute = (attribute: string): boolean => {
    return filters.some(filter => {
      if (filter.value === undefined) return false;
      // Check for exact match or if filter is on a nested property of this attribute
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

  // Handle clicking a column header to sort
  const handleColumnSort = (attribute: string) => {
    const existingSortIndex = sorts.findIndex(s => s.attribute === attribute);

    if (existingSortIndex !== -1) {
      // Column is already sorted
      const existingSort = sorts[existingSortIndex];
      if (existingSort.direction === 'asc') {
        // Change to descending
        const newSorts = [...sorts];
        newSorts[existingSortIndex] = { ...existingSort, direction: 'desc' };
        setSorts(newSorts);
      } else {
        // Remove sort
        setSorts(sorts.filter((_, i) => i !== existingSortIndex));
      }
    } else {
      // Add new sort (ascending)
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

  // Handle removing a column
  const handleRemoveColumn = (attribute: string, isDefault: boolean) => {
    // Remove from sorts if it's being sorted
    setSorts(sorts.filter(s => s.attribute !== attribute));

    // If it's an additional column, remove it from additionalColumns
    if (!isDefault) {
      setAdditionalColumns(additionalColumns.filter(col => col !== attribute));
    }
  };

  // Handle adding a new column from the sort selector
  const handleAddColumn = (attribute: ReturnType<typeof getAttributesForType>[0]) => {
    // Add to additional columns if not already there and not a default column
    const defaultColumns = getDisplayedAttributes(productType || '');
    if (!defaultColumns.includes(attribute.key) && !additionalColumns.includes(attribute.key)) {
      setAdditionalColumns([...additionalColumns, attribute.key]);
    }
    setShowSortSelector(false);
  };

  // Handle removing a sort
  const handleRemoveSort = (index: number) => {
    setSorts(sorts.filter((_, i) => i !== index));
  };

  // Handle editing sort attribute
  const handleEditSortAttribute = (index: number) => {
    // For now, just remove the sort - user can add a new one
    handleRemoveSort(index);
    setShowSortSelector(true);
  };

  if (error) {
    return (
      <div className="error">
        Error: {error}
        <button onClick={() => loadProducts(productType)} style={{ marginLeft: '0.8rem' }}>
          Retry
        </button>
      </div>
    );
  }

  // Show loading only if there are no products yet (first load)
  if (loading && products.length === 0) {
    return <div className="loading">Loading products...</div>;
  }

  return (
    <div className="page-split-layout">
      {/* Left sidebar - filter interface */}
      <aside className="filter-sidebar">
        <FilterBar
          productType={productType}
          filters={filters}
          sort={null}
          products={filteredProducts}
          onFiltersChange={setFilters}
          onSortChange={() => {}}
          onProductTypeChange={handleProductTypeChange}
        />
      </aside>

      {/* Right side - results section */}
      <main className="results-main">
        <div className="results-header">
          {/* Sort controls */}
          <div className="results-header-left">
            {sorts.length > 0 ? (
              <div className="sort-control-active">
                <span className="sort-label-inline">Sorted by:</span>
                <div className="sort-chips-container">
                  {sorts.map((sort, index) => (
                    <div
                      key={`${sort.attribute}-${index}`}
                      className={`sort-chip-draggable ${draggedSortIndex === index ? 'dragging' : ''}`}
                      draggable
                      onDragStart={() => handleDragStart(index)}
                      onDragOver={(e) => handleDragOver(e, index)}
                      onDragEnd={handleDragEnd}
                      title="Drag to reorder"
                    >
                      <span className="sort-order-number">{index + 1}</span>
                      <span
                        className="sort-attribute-inline"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEditSortAttribute(index);
                        }}
                        style={{ cursor: 'pointer' }}
                        title="Click to change attribute"
                      >
                        {sort.displayName}
                      </span>
                      <button
                        className="sort-direction-btn-inline"
                        data-direction={sort.direction}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleSortDirection(index);
                        }}
                        title={`Currently ${sort.direction === 'asc' ? 'ascending' : 'descending'} - click to reverse`}
                      >
                        {sort.direction === 'asc' ? '↑' : '↓'}
                      </button>
                      <button
                        className="sort-remove-btn-inline"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveSort(index);
                        }}
                        title="Remove this sort"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
                {sorts.length < 3 && (
                  <button
                    className="btn-add-sort-small"
                    onClick={() => {
                      setShowSortSelector(true);
                    }}
                    title="Add another sort level (max 3)"
                  >
                    + Add
                  </button>
                )}
              </div>
            ) : (
              <button
                className="btn-sort-inline"
                onClick={() => {
                  setShowSortSelector(true);
                }}
                title="Sort results by attribute"
              >
                ⇅ Sort Results
              </button>
            )}
          </div>

          <div className="results-header-right">
            {/* Refresh button */}
            <button
              className="btn-refresh"
              onClick={forceRefresh}
              disabled={loading}
              title="Force refresh data from server (clears cache)"
              style={{ marginRight: '0.8rem' }}
            >
              ↻ Refresh
            </button>
            {/* Pagination controls */}
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
              </select>
            </div>
            <span className="results-count">
              {sortedProducts.length === 0 ? '0' : `${(currentPage - 1) * itemsPerPage + 1}-${Math.min(currentPage * itemsPerPage, sortedProducts.length)}`} of {sortedProducts.length}
            </span>
            {loading && products.length > 0 && (
              <span style={{ marginLeft: '0.8rem', opacity: 0.6, fontSize: '0.8rem' }}>
                Refreshing...
              </span>
            )}
          </div>
        </div>

        {sortedProducts.length === 0 ? (
          <div className="empty-state-minimal">
            <p>
              {productType === null
                ? 'Select a product type to view products'
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
              <div className="product-grid-header-part">Part Number</div>
              {/* Default columns */}
              {getColumnHeaders().map((header) => {
                const sortIndex = sorts.findIndex(s => s.attribute === header.key);
                const isSorted = sortIndex !== -1;
                const sortConfig = isSorted ? sorts[sortIndex] : null;

                return (
                  <div
                    key={header.key}
                    className="product-grid-header-item clickable"
                    onClick={() => handleColumnSort(header.key)}
                    title="Click to sort"
                  >
                    <div className="product-grid-header-label">
                      {header.label}
                      <span className="sort-indicator">
                        {!isSorted && '⇅'}
                        {isSorted && sortConfig?.direction === 'asc' && '↑'}
                        {isSorted && sortConfig?.direction === 'desc' && '↓'}
                        {isSorted && sorts.length > 1 && <span className="sort-order">{sortIndex + 1}</span>}
                      </span>
                    </div>
                    {header.unit && <div className="product-grid-header-unit">({header.unit})</div>}
                  </div>
                );
              })}
              {/* Additional columns */}
              {additionalColumns.map((attrKey) => {
                const attributes = getAttributesForType(productType || 'motor');
                const attrMetadata = attributes.find(a => a.key === attrKey);
                if (!attrMetadata) return null;

                const firstProduct = sortedProducts[0];
                const unit = firstProduct ? extractUnit((firstProduct as any)[attrKey]) : null;

                const sortIndex = sorts.findIndex(s => s.attribute === attrKey);
                const isSorted = sortIndex !== -1;
                const sortConfig = isSorted ? sorts[sortIndex] : null;

                return (
                  <div
                    key={`additional-${attrKey}`}
                    className="product-grid-header-item clickable removable"
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
                        {!isSorted && '⇅'}
                        {isSorted && sortConfig?.direction === 'asc' && '↑'}
                        {isSorted && sortConfig?.direction === 'desc' && '↓'}
                        {isSorted && sorts.length > 1 && <span className="sort-order">{sortIndex + 1}</span>}
                      </span>
                    </div>
                    {unit && <div className="product-grid-header-unit">({unit})</div>}
                  </div>
                );
              })}
              {/* Add column button */}
              <button
                className="add-column-btn"
                onClick={() => setShowSortSelector(true)}
                title="Add column"
              >
                + Add Column
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
                    <div className="product-info-part">{product.part_number || 'N/A'}</div>
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
                          backgroundColor: proximityColor || undefined,
                          color: proximityColor ? 'white' : undefined
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
                          backgroundColor: proximityColor || undefined,
                          color: proximityColor ? 'white' : undefined
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
      />
    </div>
  );
}
