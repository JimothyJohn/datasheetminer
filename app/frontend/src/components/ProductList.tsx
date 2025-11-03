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
  const [productType, setProductType] = useState<ProductType>('all');
  const [filters, setFilters] = useState<FilterCriterion[]>([]);
  const [sorts, setSorts] = useState<SortConfig[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [clickPosition, setClickPosition] = useState<{ x: number; y: number } | null>(null);
  const [showSortSelector, setShowSortSelector] = useState(false);
  const [editingSortIndex, setEditingSortIndex] = useState<number | null>(null);
  const [draggedSortIndex, setDraggedSortIndex] = useState<number | null>(null);
  const [itemsPerPage, setItemsPerPage] = useState<number>(25);
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Load products and categories when product type changes or on mount
  useEffect(() => {
    loadProducts(productType);
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

  // Handle sort selection (add or edit)
  const handleSortSelect = (attribute: typeof availableAttributes[0]) => {
    if (editingSortIndex !== null) {
      // Edit existing sort - preserve direction
      const existingSort = sorts[editingSortIndex];
      const updatedSort: SortConfig = {
        ...existingSort,
        attribute: attribute.key,
        displayName: attribute.displayName
      };
      const newSorts = [...sorts];
      newSorts[editingSortIndex] = updatedSort;
      setSorts(newSorts);
      setEditingSortIndex(null);
    } else {
      // Check if this attribute is already being sorted
      const existingIndex = sorts.findIndex(s => s.attribute === attribute.key);

      if (existingIndex !== -1) {
        // Toggle direction if same attribute already exists
        const newSorts = [...sorts];
        newSorts[existingIndex] = {
          ...newSorts[existingIndex],
          direction: newSorts[existingIndex].direction === 'asc' ? 'desc' : 'asc'
        };
        setSorts(newSorts);
      } else {
        // Add new sort (max 3 sorts)
        const newSort: SortConfig = {
          attribute: attribute.key,
          direction: 'asc',
          displayName: attribute.displayName
        };
        setSorts(prev => [...prev, newSort].slice(0, 3)); // Limit to 3 sorts
      }
    }
    setShowSortSelector(false);
  };

  // Handle clicking on sort attribute to edit it
  const handleEditSortAttribute = (index: number) => {
    setEditingSortIndex(index);
    setShowSortSelector(true);
  };

  // Handle removing a specific sort
  const handleRemoveSort = (index: number) => {
    setSorts(prev => prev.filter((_, i) => i !== index));
  };

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
      return ['rated_power', 'rated_voltage', 'rated_current'];
    } else if (productType === 'drive') {
      return ['output_power', 'input_voltage', 'rated_current'];
    }
    return [];
  };

  // Get sort values for a product (only those NOT already displayed in main specs)
  const getSortValues = (product: Product): Array<{ label: string; value: string }> => {
    const displayedAttrs = getDisplayedAttributes(product.product_type);

    return sorts
      .filter(sort => !displayedAttrs.includes(sort.attribute))
      .map(sort => ({
        label: sort.displayName,
        value: formatValue((product as any)[sort.attribute])
      }));
  };

  // Extract numeric value from a value object
  const extractNumericValue = (value: any): number | null => {
    if (!value) return null;
    if (typeof value === 'number') return value;
    if (typeof value === 'object') {
      if ('value' in value && typeof value.value === 'number') return value.value;
      if ('nominal' in value && typeof value.nominal === 'number') return value.nominal;
      if ('rated' in value && typeof value.rated === 'number') return value.rated;
      if ('min' in value && 'max' in value) {
        return (Number(value.min) + Number(value.max)) / 2;
      }
    }
    return null;
  };

  // Get color based on proximity to filter value
  const getProximityColor = (attribute: string, productValue: any): string => {
    // Find if there's a filter for this attribute
    const filter = filters.find(f => f.attribute === attribute);
    if (!filter || filter.operator === '!=') return '';

    const numericProductValue = extractNumericValue(productValue);
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

  // Check if an attribute is currently being filtered
  const isFilteredAttribute = (attribute: string): boolean => {
    return filters.some(filter => filter.attribute === attribute && filter.value !== undefined);
  };

  const handleProductClick = (product: Product, event: React.MouseEvent) => {
    setClickPosition({ x: event.clientX, y: event.clientY });
    setSelectedProduct(product);
  };

  const handleCloseModal = () => {
    setSelectedProduct(null);
    setClickPosition(null);
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
                      setEditingSortIndex(null);
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
                  setEditingSortIndex(null);
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
              style={{
                padding: '0.35rem 0.7rem',
                fontSize: '0.8rem',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.5 : 1,
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                background: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                marginRight: '0.8rem'
              }}
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
              {products.length === 0
                ? 'No products in database'
                : 'No results match your filters'}
            </p>
          </div>
        ) : (
          <>
            <div className="product-grid">
              {paginatedProducts.map((product) => (
                <div
                  key={product.product_id}
                  className="product-card-minimal"
                  onClick={(e) => handleProductClick(product, e)}
                >
                  <div className="product-card-header">
                    <span className="product-part">{product.part_number || 'N/A'}</span>
                    <span className="product-manufacturer">{product.manufacturer || 'Unknown'}</span>
                  </div>
                  <div className="product-card-specs">
                    {product.product_type === 'motor' && (
                      <>
                        {'rated_power' in product && product.rated_power && (() => {
                          const proximityColor = getProximityColor('rated_power', product.rated_power);
                          const hasProximityColor = !!proximityColor;
                          return (
                            <span
                              className={`spec-item ${
                                !hasProximityColor && isFilteredAttribute('rated_power') ? 'spec-item-filtered' :
                                !hasProximityColor && isSortedAttribute('rated_power') ? 'spec-item-sorted' : ''
                              }`}
                              style={{
                                backgroundColor: proximityColor || undefined,
                                color: proximityColor ? 'white' : undefined,
                                fontWeight: proximityColor ? 700 : undefined
                              }}
                            >
                              Power: {formatValue(product.rated_power)}
                            </span>
                          );
                        })()}
                        {'rated_voltage' in product && product.rated_voltage && (() => {
                          const proximityColor = getProximityColor('rated_voltage', product.rated_voltage);
                          const hasProximityColor = !!proximityColor;
                          return (
                            <span
                              className={`spec-item ${
                                !hasProximityColor && isFilteredAttribute('rated_voltage') ? 'spec-item-filtered' :
                                !hasProximityColor && isSortedAttribute('rated_voltage') ? 'spec-item-sorted' : ''
                              }`}
                              style={{
                                backgroundColor: proximityColor || undefined,
                                color: proximityColor ? 'white' : undefined,
                                fontWeight: proximityColor ? 700 : undefined
                              }}
                            >
                              Voltage: {formatValue(product.rated_voltage)}
                            </span>
                          );
                        })()}
                        {'rated_current' in product && product.rated_current && (() => {
                          const proximityColor = getProximityColor('rated_current', product.rated_current);
                          const hasProximityColor = !!proximityColor;
                          return (
                            <span
                              className={`spec-item ${
                                !hasProximityColor && isFilteredAttribute('rated_current') ? 'spec-item-filtered' :
                                !hasProximityColor && isSortedAttribute('rated_current') ? 'spec-item-sorted' : ''
                              }`}
                              style={{
                                backgroundColor: proximityColor || undefined,
                                color: proximityColor ? 'white' : undefined,
                                fontWeight: proximityColor ? 700 : undefined
                              }}
                            >
                              Current: {formatValue(product.rated_current)}
                            </span>
                          );
                        })()}
                      </>
                    )}
                    {product.product_type === 'drive' && (
                      <>
                        {'output_power' in product && product.output_power && (() => {
                          const proximityColor = getProximityColor('output_power', product.output_power);
                          const hasProximityColor = !!proximityColor;
                          return (
                            <span
                              className={`spec-item ${
                                !hasProximityColor && isFilteredAttribute('output_power') ? 'spec-item-filtered' :
                                !hasProximityColor && isSortedAttribute('output_power') ? 'spec-item-sorted' : ''
                              }`}
                              style={{
                                backgroundColor: proximityColor || undefined,
                                color: proximityColor ? 'white' : undefined,
                                fontWeight: proximityColor ? 700 : undefined
                              }}
                            >
                              Power: {formatValue(product.output_power)}
                            </span>
                          );
                        })()}
                        {'input_voltage' in product && product.input_voltage && (() => {
                          const proximityColor = getProximityColor('input_voltage', product.input_voltage);
                          const hasProximityColor = !!proximityColor;
                          return (
                            <span
                              className={`spec-item ${
                                !hasProximityColor && isFilteredAttribute('input_voltage') ? 'spec-item-filtered' :
                                !hasProximityColor && isSortedAttribute('input_voltage') ? 'spec-item-sorted' : ''
                              }`}
                              style={{
                                backgroundColor: proximityColor || undefined,
                                color: proximityColor ? 'white' : undefined,
                                fontWeight: proximityColor ? 700 : undefined
                              }}
                            >
                              Voltage: {formatValue(product.input_voltage)}
                            </span>
                          );
                        })()}
                        {'rated_current' in product && product.rated_current && (() => {
                          const proximityColor = getProximityColor('rated_current', product.rated_current);
                          const hasProximityColor = !!proximityColor;
                          return (
                            <span
                              className={`spec-item ${
                                !hasProximityColor && isFilteredAttribute('rated_current') ? 'spec-item-filtered' :
                                !hasProximityColor && isSortedAttribute('rated_current') ? 'spec-item-sorted' : ''
                              }`}
                              style={{
                                backgroundColor: proximityColor || undefined,
                                color: proximityColor ? 'white' : undefined,
                                fontWeight: proximityColor ? 700 : undefined
                              }}
                            >
                              Current: {formatValue(product.rated_current)}
                            </span>
                          );
                        })()}
                      </>
                    )}
                  </div>
                  {/* Show sorted values if sorting is active */}
                  {sorts.length > 0 && (
                    <div className="product-sort-values">
                      {getSortValues(product).map((sortValue, idx) => (
                        <div key={idx} className="product-sort-value">
                          <span className="sort-value-order">{idx + 1}</span>
                          <span className="sort-value-label">{sortValue.label}:</span>
                          <span className="sort-value-content">{sortValue.value}</span>
                        </div>
                      ))}
                    </div>
                  )}
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

      {/* Attribute Selector Modal for Sort */}
      <AttributeSelector
        attributes={availableAttributes}
        onSelect={handleSortSelect}
        onClose={() => {
          setShowSortSelector(false);
          setEditingSortIndex(null);
        }}
        isOpen={showSortSelector}
      />
    </div>
  );
}
