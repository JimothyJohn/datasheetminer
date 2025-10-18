/**
 * Product list component with advanced filtering and sorting
 */

import { useState, useEffect, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { ProductType, Product } from '../types/models';
import { FilterCriterion, SortConfig, applyFilters, sortProducts, getAttributesForType } from '../types/filters';
import FilterBar from './FilterBar';
import ProductDetailModal from './ProductDetailModal';
import AttributeSelector from './AttributeSelector';

export default function ProductList() {
  const { products, loading, error, loadProducts } = useApp();
  const [productType, setProductType] = useState<ProductType>('all');
  const [filters, setFilters] = useState<FilterCriterion[]>([]);
  const [sorts, setSorts] = useState<SortConfig[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [clickPosition, setClickPosition] = useState<{ x: number; y: number } | null>(null);
  const [showSortSelector, setShowSortSelector] = useState(false);
  const [draggedSortIndex, setDraggedSortIndex] = useState<number | null>(null);

  // Load products when product type changes or on mount
  useEffect(() => {
    loadProducts(productType);
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

  // Get available attributes for sorting based on filtered results
  // Filter out attributes where all filtered products have the same value
  const availableAttributes = useMemo(() => {
    const allAttributes = getAttributesForType(productType);
    if (filteredProducts.length === 0) return allAttributes;

    return allAttributes.filter(attr => {
      // Check if attribute exists in any product
      const valuesWithAttribute = filteredProducts.filter(product => {
        const value = (product as any)[attr.key];
        return value !== undefined && value !== null;
      });

      if (valuesWithAttribute.length === 0) return false;

      // Get all unique values for this attribute
      const uniqueValues = new Set();
      valuesWithAttribute.forEach(product => {
        const value = (product as any)[attr.key];
        // Normalize the value for comparison
        let normalizedValue: string;
        if (typeof value === 'object' && value !== null) {
          // Handle ValueUnit, MinMaxUnit, arrays, etc.
          normalizedValue = JSON.stringify(value);
        } else {
          normalizedValue = String(value);
        }
        uniqueValues.add(normalizedValue);
      });

      // Only include if there are multiple different values
      return uniqueValues.size > 1;
    });
  }, [filteredProducts, productType]);

  // Handle sort selection
  const handleSortSelect = (attribute: typeof availableAttributes[0]) => {
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
    setShowSortSelector(false);
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

  const formatValue = (value: any): string => {
    if (!value) return 'N/A';
    if (typeof value === 'object' && 'value' in value && 'unit' in value) {
      return `${value.value} ${value.unit}`;
    }
    if (typeof value === 'object' && 'min' in value && 'max' in value && 'unit' in value) {
      return `${value.min}-${value.max} ${value.unit}`;
    }
    return String(value);
  };

  // Get sort values for a product (all active sorts)
  const getSortValues = (product: Product): Array<{ label: string; value: string }> => {
    return sorts.map(sort => ({
      label: sort.displayName,
      value: formatValue((product as any)[sort.attribute])
    }));
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
        <button onClick={() => loadProducts(productType)} style={{ marginLeft: '1rem' }}>
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
          <div className="results-header-left">
            <span className="results-count">
              {sortedProducts.length} {sortedProducts.length === 1 ? 'result' : 'results'}
            </span>
            {loading && products.length > 0 && (
              <span style={{ marginLeft: '1rem', opacity: 0.6, fontSize: '0.9rem' }}>
                Refreshing...
              </span>
            )}
          </div>

          {/* Sort controls */}
          <div className="results-header-right">
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
                      <span className="sort-attribute-inline">{sort.displayName}</span>
                      <button
                        className="sort-direction-btn-inline"
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
                    onClick={() => setShowSortSelector(true)}
                    title="Add another sort level (max 3)"
                  >
                    + Add
                  </button>
                )}
              </div>
            ) : (
              <button
                className="btn-sort-inline"
                onClick={() => setShowSortSelector(true)}
                title="Sort results by attribute"
              >
                ⇅ Sort Results
              </button>
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
          <div className="product-grid">
            {sortedProducts.map((product) => (
              <div
                key={product.product_id}
                className="product-card-minimal"
                onClick={(e) => handleProductClick(product, e)}
              >
                <div className="product-card-header">
                  <span className="product-manufacturer">{product.manufacturer || 'Unknown'}</span>
                  <span className="product-part">{product.part_number || 'N/A'}</span>
                </div>
                <div className="product-card-specs">
                  {product.product_type === 'motor' && 'rated_power' in product && (
                    <span className="spec-item">
                      Power: {formatValue(product.rated_power)}
                    </span>
                  )}
                  {product.product_type === 'drive' && 'output_power' in product && (
                    <span className="spec-item">
                      Power: {formatValue(product.output_power)}
                    </span>
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
        onClose={() => setShowSortSelector(false)}
        isOpen={showSortSelector}
      />
    </div>
  );
}
