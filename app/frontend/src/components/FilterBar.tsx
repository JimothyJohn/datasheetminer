/**
 * Main filter bar component with attribute selection and filter management
 */

import { useState, useMemo } from 'react';
import { FilterCriterion, SortConfig, getAttributesForType, getAvailableOperators, applyFilters, deriveAttributesFromRecords, mergeAttributesByKey } from '../types/filters';
import { orderColumnAttributes } from '../types/columnOrder';
import { ProductType, Product } from '../types/models';
import { extractUniqueValues } from '../utils/filterValues';
import { useApp } from '../context/AppContext';
import AttributeSelector from './AttributeSelector';
import FilterChip from './FilterChip';
import DistributionChart from './DistributionChart';
import Dropdown from './Dropdown';

interface FilterBarProps {
  productType: ProductType;
  filters: FilterCriterion[];
  sort: SortConfig | null;
  products: Product[];
  onFiltersChange: (filters: FilterCriterion[]) => void;
  onSortChange: (sort: SortConfig | null) => void;
  onSortByOperator?: (attribute: string, displayName: string, direction: 'asc' | 'desc') => void;
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
  onSortByOperator,
  onProductTypeChange,
  allProducts
}: FilterBarProps) {
  const [showAttributeSelector, setShowAttributeSelector] = useState(false);
  const [editingFilterIndex, setEditingFilterIndex] = useState<number | null>(null);
  // Cursor anchor for the AttributeSelector — captured at click time so
  // the picker drops where the pointer is, not back near the button the
  // user already moved away from.
  const [selectorCursor, setSelectorCursor] = useState<{ x: number; y: number } | null>(null);

  // Get categories from context for dynamic dropdown
  const { categories } = useApp();

  // Attribute list for the current product type. Starts from the
  // rich per-type static defs (nice display names + tuned units) then
  // appends any keys the actual records carry but the static list
  // doesn't. Then sorted with the same COLUMN_ORDER the results table
  // uses, so the most-important filter attributes appear first in the
  // selector — matching the left-to-right column priority a user already
  // sees in the table.
  const availableAttributes = useMemo(() => {
    const staticAttrs = getAttributesForType(productType);
    const derivedAttrs = deriveAttributesFromRecords(products, productType);
    const merged = mergeAttributesByKey(staticAttrs, derivedAttrs);
    return orderColumnAttributes(merged, productType);
  }, [productType, products]);

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
    // Default to >= for numeric/slider fields, = for string-only fields
    const hasComparison = availableOperators.some(op => op === '>' || op === '>=' || op === '<' || op === '<=');
    const defaultOperator = hasComparison ? '>=' : (availableOperators.length > 0 ? availableOperators[0] : '=');

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
  const handleEditFilterAttribute = (index: number, cursor: { x: number; y: number } | null) => {
    setEditingFilterIndex(index);
    setSelectorCursor(cursor);
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
        <Dropdown<string>
          value={productType === null ? '' : productType}
          onChange={(v) => onProductTypeChange(v === '' ? null : (v as ProductType))}
          disabled={categories.length === 0}
          fullWidth
          ariaLabel="Product type"
          placeholder={categories.length === 0 ? 'Loading...' : 'Select Product Type...'}
          options={[
            { value: '', label: categories.length === 0 ? 'Loading...' : 'Select Product Type...' },
            ...categories.map((category) => ({
              value: category.type,
              label: category.display_name,
            })),
          ]}
        />
      </div>

      <h2 className="filter-sidebar-title">Specs</h2>

      {/* Match summary — total vs filtered, with percentage bar. Anchors
       * the top of the pane so the impact of every chip is visible
       * without scrolling to the table. Hidden when no product type is
       * selected (allProducts is empty). */}
      {productType && allProducts.length > 0 && (
        <div className="filter-match-summary">
          <div className="filter-match-numbers">
            <span className="filter-match-count">{products.length}</span>
            <span className="filter-match-divider">/</span>
            <span className="filter-match-total">{allProducts.length}</span>
            <span className="filter-match-label">matching</span>
          </div>
          <div className="filter-match-bar" aria-hidden="true">
            <div
              className="filter-match-bar-fill"
              style={{
                width: `${allProducts.length === 0 ? 0 : (products.length / allProducts.length) * 100}%`,
              }}
            />
          </div>
          <div className="filter-match-meta">
            <span>
              {filters.length === 0
                ? 'no specs active'
                : `${filters.length} spec${filters.length === 1 ? '' : 's'} active`}
            </span>
            <span className="filter-match-percent">
              {allProducts.length === 0
                ? '0%'
                : `${Math.round((products.length / allProducts.length) * 100)}%`}
            </span>
          </div>
        </div>
      )}

      {/* Action buttons — fixed position, never jump */}
      <div className="filter-actions-container">
        <button
          className="btn-add-filter"
          onClick={(e) => {
            setEditingFilterIndex(null);
            setSelectorCursor({ x: e.clientX, y: e.clientY });
            setShowAttributeSelector(true);
          }}
          title="Add spec (Ctrl+K)"
        >
          + Add Spec
        </button>
        {(filters.length > 0 || sort) && (
          <button
            className="btn-clear"
            onClick={handleClearFilters}
            title="Clear all specs and sorts"
          >
            Clear All
          </button>
        )}
      </div>

      {/* Filter rows — each row pairs a chip with its distribution chart
       * so the data shape sits directly under the filter that produced
       * it. Previously the chips and charts were rendered in two
       * disconnected loops, which forced the user to mentally pair them. */}
      <div className="filter-chips-container">
        {filters.map((filter, index) => {
          const attributeMetadata = availableAttributes.find(
            attr => attr.key === filter.attribute
          );

          const otherFilters = filters.filter((_, i) => i !== index);
          const contextProducts = otherFilters.length === 0
            ? allProducts
            : applyFilters(allProducts, otherFilters);

          return (
            <div key={`${filter.attribute}-${index}`} className="filter-row">
              <FilterChip
                filter={filter}
                attributeType={attributeMetadata?.type}
                attributeMetadata={attributeMetadata}
                products={products}
                suggestedValues={suggestedValuesByAttribute.get(filter.attribute) || []}
                onUpdate={(updated) => handleUpdateFilter(index, updated)}
                onRemove={() => handleRemoveFilter(index)}
                onEditAttribute={(cursor) => handleEditFilterAttribute(index, cursor)}
                onSortByOperator={onSortByOperator}
                allProducts={contextProducts}
              />
              {products.length > 0 && (
                <DistributionChart
                  products={products}
                  attribute={filter.attribute}
                  title={filter.displayName}
                  attributeType={attributeMetadata?.type}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Attribute Selector Modal for Filters */}
      <AttributeSelector
        attributes={availableAttributes}
        onSelect={handleAddOrEditFilter}
        onClose={() => {
          setShowAttributeSelector(false);
          setEditingFilterIndex(null);
          setSelectorCursor(null);
        }}
        isOpen={showAttributeSelector}
        cursorPosition={selectorCursor}
      />
    </div>
  );
}
