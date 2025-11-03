/**
 * Main filter bar component with attribute selection and filter management
 */

import { useState, useMemo } from 'react';
import { FilterCriterion, SortConfig, getAttributesForType } from '../types/filters';
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
    // Only add operator for numeric types (number, object, range)
    const isNumericType = ['number', 'object', 'range'].includes(attribute.type);

    if (editingFilterIndex !== null) {
      // Edit existing filter - preserve value and operator
      const existingFilter = filters[editingFilterIndex];
      const updatedFilter: FilterCriterion = {
        ...existingFilter,
        attribute: attribute.key,
        displayName: attribute.displayName,
        // Only preserve operator if the new attribute is also numeric
        ...(isNumericType ? {} : { operator: undefined }),
        // If changing to a different attribute, clear the value
        value: undefined,
      };
      const newFilters = [...filters];
      newFilters[editingFilterIndex] = updatedFilter;
      onFiltersChange(newFilters);
      setEditingFilterIndex(null);
    } else {
      // Add new filter
      const newFilter: FilterCriterion = {
        attribute: attribute.key,
        mode: 'include',
        ...(isNumericType && { operator: '=' }), // Only add operator for numeric types
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
          value={productType}
          onChange={(e) => onProductTypeChange(e.target.value as ProductType)}
          className="product-type-select"
        >
          <option value="all">All Products</option>
          {categories.map((category) => (
            <option key={category.type} value={category.type}>
              {category.display_name}
            </option>
          ))}
        </select>
      </div>

      <h2 className="filter-sidebar-title">Filters</h2>

      {/* Add filter button - at the top */}
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
              suggestedValues={suggestedValuesByAttribute.get(filter.attribute) || []}
              onUpdate={(updated) => handleUpdateFilter(index, updated)}
              onRemove={() => handleRemoveFilter(index)}
              onEditAttribute={() => handleEditFilterAttribute(index)}
            />
          );
        })}
      </div>

      {/* Clear all button - at the bottom to avoid accidental clicks */}
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
