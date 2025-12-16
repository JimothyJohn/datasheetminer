import React, { useState, useRef } from 'react';
import { FilterCriterion, getDatasheetAttributes, AttributeMetadata } from '../types/filters';
import { DatasheetEntry, Product } from '../types/models';
import AttributeSelector from './AttributeSelector';
import FilterChip from './FilterChip';

interface DatasheetFilterBarProps {
  filters: FilterCriterion[];
  datasheets: DatasheetEntry[];
  onFiltersChange: (filters: FilterCriterion[]) => void;
}

export default function DatasheetFilterBar({
  filters,
  datasheets,
  onFiltersChange,
}: DatasheetFilterBarProps) {
  const [isAttributeSelectorOpen, setIsAttributeSelectorOpen] = useState(false);
  const addFilterButtonRef = useRef<HTMLButtonElement>(null);
  
  const handleAddFilter = (attributeMeta: AttributeMetadata) => {
    const attribute = attributeMeta.key;
    if (filters.some(f => f.attribute === attribute)) return;
    
    const newFilter: FilterCriterion = {
      attribute,
      operator: '=',
      value: '',
      mode: 'include',
      displayName: attributeMeta.displayName
    };

    onFiltersChange([...filters, newFilter]);
  };

  const handleRemoveFilter = (index: number) => {
    const newFilters = [...filters];
    newFilters.splice(index, 1);
    onFiltersChange(newFilters);
  };

  const handleUpdateFilter = (index: number, updates: Partial<FilterCriterion>) => {
    const newFilters = [...filters];
    newFilters[index] = { ...newFilters[index], ...updates };
    onFiltersChange(newFilters);
  };

  const datasheetAttributes = getDatasheetAttributes();

  return (
    <div className="filter-bar-minimal">
      <div className="filter-bar-controls">
        {/* Add Filter Button */}

        <div className="filter-actions">
          <button
            ref={addFilterButtonRef}
            className="btn-secondary btn-sm"
            onClick={() => setIsAttributeSelectorOpen(true)}
          >
            + Add Filter
          </button>
          
          <AttributeSelector
            attributes={datasheetAttributes}
            onSelect={handleAddFilter}
            onClose={() => setIsAttributeSelectorOpen(false)}
            isOpen={isAttributeSelectorOpen}
            anchorElement={addFilterButtonRef.current}
          />
        </div>
      </div>

      {/* Active Filters Chips */}
      {filters.length > 0 && (
        <div className="filter-chips-container">
          {filters.map((filter, index) => {
            // Extract unique values for this attribute to populate dropdown
            const uniqueValues = Array.from(new Set(
              datasheets
                .map(ds => (ds as any)[filter.attribute])
                .filter(val => val !== undefined && val !== null && val !== '')
            )).sort();

            return (
              <div key={`${filter.attribute}-${index}`} className="filter-chip-minimal">
                <FilterChip
                  filter={filter}
                  products={datasheets as unknown as Product[]} // Cast to Product[] for compatibility
                  onRemove={() => {
                     const realIndex = filters.indexOf(filter);
                     if (realIndex !== -1) handleRemoveFilter(realIndex);
                  }}
                  onUpdate={(updates) => {
                     const realIndex = filters.indexOf(filter);
                     if (realIndex !== -1) handleUpdateFilter(realIndex, updates);
                  }}
                  onEditAttribute={() => {}} // No-op for now
                  attributeMetadata={datasheetAttributes.find(a => a.key === filter.attribute)}
                  suggestedValues={uniqueValues as string[]}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
