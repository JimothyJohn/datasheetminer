/**
 * Main filter bar component with attribute selection and filter management
 */

import { useState, useMemo } from 'react';
import { FilterCriterion, SortConfig, getAttributesForType, getAvailableOperators, applyFilters } from '../types/filters';
import { ProductType, Product } from '../types/models';
import { extractUniqueValues } from '../utils/filterValues';
import { useApp } from '../context/AppContext';
import AttributeSelector from './AttributeSelector';
import FilterChip from './FilterChip';
import DistributionChart from './DistributionChart';

interface FilterBarProps {
  productType: ProductType;
  filters: FilterCriterion[];
  sort: SortConfig | null;
  products: Product[];
  onFiltersChange: (filters: FilterCriterion[]) => void;
  onSortChange: (sort: SortConfig | null) => void;
  onProductTypeChange: (type: ProductType) => void;
  allProducts: Product[];
}

export default function FilterBar({
  productType,
  filters,
  sort,
  products,
  onFiltersChange,
  onSortChange,
  onProductTypeChange,
  allProducts
}: FilterBarProps) {
  const [showAttributeSelector, setShowAttributeSelector] = useState(false);
  const [editingFilterIndex, setEditingFilterIndex] = useState<number | null>(null);

  // Get categories from context for dynamic dropdown
  const { categories } = useApp();

  // Get all available attributes for the current product type
  const availableAttributes = useMemo(() => {
    return getAttributesForType(productType);
  }, [productType]);

  // Memoize suggested values for each attribute
  const suggestedValuesByAttribute = useMemo(() => {
    const cache = new Map<string, Array<string | number>>();

    filters.forEach(filter => {
      if (!cache.has(filter.attribute)) {
        cache.set(filter.attribute, extractUniqueValues(products, filter.attribute));
      }
    });

    return cache;
  }, [products, filters]);

  // Handle adding a new filter or editing an existing one
  const handleAddOrEditFilter = (attribute: typeof availableAttributes[0]) => {
    // Get available operators for this attribute based on actual data
    const availableOperators = getAvailableOperators(products, attribute.key);
    const defaultOperator = availableOperators.length > 0 ? availableOperators[0] : '=';

    if (editingFilterIndex !== null) {
      // Edit existing filter - preserve value and operator if valid, otherwise use default
      const existingFilter = filters[editingFilterIndex];
      const isOperatorValid = availableOperators.includes(existingFilter.operator || '=');

      const updatedFilter: FilterCriterion = {
        ...existingFilter,
        attribute: attribute.key,
        displayName: attribute.displayName,
        // Use existing operator if valid, otherwise use default
        operator: isOperatorValid ? existingFilter.operator : defaultOperator,
        // If changing to a different attribute, clear the value
        value: undefined,
      };
      const newFilters = [...filters];
      newFilters[editingFilterIndex] = updatedFilter;
      onFiltersChange(newFilters);
      setEditingFilterIndex(null);
    } else {
      // Add new filter with appropriate default operator
      const newFilter: FilterCriterion = {
        attribute: attribute.key,
        mode: 'include',
        operator: defaultOperator,
        displayName: attribute.displayName,
      };
      onFiltersChange([...filters, newFilter]);
    }
    setShowAttributeSelector(false);
  };

  // Handle clicking on filter attribute to edit it
  const handleEditFilterAttribute = (index: number) => {
    setEditingFilterIndex(index);
    setShowAttributeSelector(true);
  };

  // Handle updating a filter
  const handleUpdateFilter = (index: number, updatedFilter: FilterCriterion) => {
    const newFilters = [...filters];
    newFilters[index] = updatedFilter;
    onFiltersChange(newFilters);
  };

  // Handle removing a filter
  const handleRemoveFilter = (index: number) => {
    const newFilters = filters.filter((_, i) => i !== index);
    onFiltersChange(newFilters);
  };

  const handleClearFilters = () => {
    onFiltersChange([]);
    onSortChange(null);
  };

  return (
    <div className="filter-bar-minimal">
      {/* Product type selector at the top - dynamically populated */}
      <div className="filter-controls-top">
        <select
          value={productType === null ? '' : productType}
          onChange={(e) => onProductTypeChange(e.target.value === '' ? null : e.target.value as ProductType)}
          className="product-type-select"
        >
          <option value="">Select Product Type...</option>
          {categories.map((category) => (
            <option key={category.type} value={category.type}>
              {category.display_name}
            </option>
          ))}
        </select>
      </div>

      <h2 className="filter-sidebar-title">Filters</h2>

      {/* Clear all button - at the top */}
      {(filters.length > 0 || sort) && (
        <div className="filter-clear-container">
          <button
            className="btn-clear"
            onClick={handleClearFilters}
            title="Clear all filters and sorts"
            style={{ color: '#ef4444' }}
          >
            Clear All Filters
          </button>
        </div>
      )}

      {/* Filter chips - populate below */}
      <div className="filter-chips-container">
        {filters.map((filter, index) => {
          // Find attribute metadata for this filter
          const attributeMetadata = availableAttributes.find(
            attr => attr.key === filter.attribute
          );

          // Calculate context products for this filter (apply all OTHER filters)
          // This ensures the slider range reflects the current search context (faceted navigation)
          // but doesn't disappear when the current filter excludes everything.
          const otherFilters = filters.filter((_, i) => i !== index);
          // We need to import applyFilters if it's not already imported or available in scope
          // It is imported at the top of the file.
          // However, applyFilters is expensive, so we should be careful.
          // But for this feature it's necessary.
          // Note: applyFilters is imported from '../types/filters'
          
          // Optimization: If no other filters, context is allProducts
          const contextProducts = otherFilters.length === 0 
            ? allProducts 
            : (() => {
                // We need to use the applyFilters function imported from '../types/filters'
                // But we can't call it inside the render loop easily without performance impact if many filters.
                // For now, we'll do it directly.
                // Actually, let's use a useMemo for the whole list if possible, but it depends on index.
                // Since we are inside map, we can't use hooks.
                // We will rely on the fact that applyFilters is reasonably fast (client-side).
                
                // We need to import applyFilters. It's not imported in the original file content I saw?
                // Let me check the imports in FilterBar.tsx again.
                return applyFilters(allProducts, otherFilters);
              })();

          return (
            <FilterChip
              key={`${filter.attribute}-${index}`}
              filter={filter}
              attributeType={attributeMetadata?.type}
              attributeMetadata={attributeMetadata}
              products={products}
              suggestedValues={suggestedValuesByAttribute.get(filter.attribute) || []}
              onUpdate={(updated) => handleUpdateFilter(index, updated)}
              onRemove={() => handleRemoveFilter(index)}
              onEditAttribute={() => handleEditFilterAttribute(index)}
              allProducts={contextProducts}
            />
          );
        })}
      </div>

      {/* Add filter button - at the bottom */}
      <div className="filter-add-container" style={{ marginTop: filters.length === 0 ? '0.5rem' : undefined }}>
        <button
          className="btn-add-filter"
          onClick={() => {
            setEditingFilterIndex(null);
            setShowAttributeSelector(true);
          }}
          title="Add filter (Ctrl+K)"
        >
          + Add Filter
        </button>
      </div>

      {/* Attribute Selector Modal for Filters */}
      <AttributeSelector
        attributes={availableAttributes}
        onSelect={handleAddOrEditFilter}
        onClose={() => {
          setShowAttributeSelector(false);
          setEditingFilterIndex(null);
        }}
        isOpen={showAttributeSelector}
      />

      {/* Distribution Charts for Active Filters */}
      {products.length > 0 && filters.map((filter) => (
        <DistributionChart 
          key={`chart-${filter.attribute}`}
          products={products}
          attribute={filter.attribute}
          title={filter.displayName}
        />
      ))}
    </div>
  );
}
