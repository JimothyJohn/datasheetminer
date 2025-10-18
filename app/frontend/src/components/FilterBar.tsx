/**
 * Main filter bar component with attribute selection and filter management
 */

import { useState, useMemo } from 'react';
import { FilterCriterion, SortConfig, getAttributesForType } from '../types/filters';
import { ProductType, Product } from '../types/models';
import { extractUniqueValues } from '../utils/filterValues';
import AttributeSelector from './AttributeSelector';
import FilterChip from './FilterChip';

interface FilterBarProps {
  productType: ProductType;
  filters: FilterCriterion[];
  sort: SortConfig | null;
  products: Product[];
  onFiltersChange: (filters: FilterCriterion[]) => void;
  onSortChange: (sort: SortConfig | null) => void;
  onProductTypeChange: (type: ProductType) => void;
}

export default function FilterBar({
  productType,
  filters,
  sort,
  products,
  onFiltersChange,
  onSortChange,
  onProductTypeChange
}: FilterBarProps) {
  const [showAttributeSelector, setShowAttributeSelector] = useState(false);

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

  // Handle adding a new filter
  const handleAddFilter = (attribute: typeof availableAttributes[0]) => {
    const newFilter: FilterCriterion = {
      attribute: attribute.key,
      mode: 'include',
      operator: '=',
      displayName: attribute.displayName,
    };
    onFiltersChange([...filters, newFilter]);
    setShowAttributeSelector(false);
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
      {/* Product type selector at the top */}
      <div className="filter-controls-top">
        <select
          value={productType}
          onChange={(e) => onProductTypeChange(e.target.value as ProductType)}
          className="product-type-select"
        >
          <option value="all">All Products</option>
          <option value="motor">Motors</option>
          <option value="drive">Drives</option>
        </select>
      </div>

      <h2 className="filter-sidebar-title">Filters</h2>

      {/* Add filter button - at the top */}
      <div className="filter-add-container">
        <button
          className="btn-add-filter"
          onClick={() => setShowAttributeSelector(true)}
          title="Add filter (Ctrl+K)"
        >
          + Add Filter
        </button>
        <span className="hint-text">Press Ctrl+K to add filter</span>
      </div>

      {/* Clear all button */}
      {(filters.length > 0 || sort) && (
        <div className="filter-clear-container">
          <button
            className="btn-clear"
            onClick={handleClearFilters}
            title="Clear all"
          >
            Clear All Filters
          </button>
        </div>
      )}

      {/* Filter chips - populate below */}
      <div className="filter-chips-container">
        {filters.map((filter, index) => (
          <FilterChip
            key={`${filter.attribute}-${index}`}
            filter={filter}
            suggestedValues={suggestedValuesByAttribute.get(filter.attribute) || []}
            onUpdate={(updated) => handleUpdateFilter(index, updated)}
            onRemove={() => handleRemoveFilter(index)}
          />
        ))}
      </div>

      {/* Attribute Selector Modal for Filters */}
      <AttributeSelector
        attributes={availableAttributes}
        onSelect={handleAddFilter}
        onClose={() => setShowAttributeSelector(false)}
        isOpen={showAttributeSelector}
      />
    </div>
  );
}
