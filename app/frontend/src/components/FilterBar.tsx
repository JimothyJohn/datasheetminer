/**
 * Main filter bar component with attribute selection and filter management
 */

import { useState, useMemo } from 'react';
import { FilterCriterion, SortConfig, getAttributesForType, getAvailableOperators } from '../types/filters';
import { ProductType, Product } from '../types/models';
import { extractUniqueValues } from '../utils/filterValues';
import { useApp } from '../context/AppContext';
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
            />
          );
        })}
      </div>

      {/* Add filter button - at the bottom */}
      <div className="filter-add-container">
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
        <span className="hint-text">Press Ctrl+K to add filter</span>
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
    </div>
  );
}
