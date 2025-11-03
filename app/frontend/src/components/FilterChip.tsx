/**
 * Filter chip component with comparison operators
 * Minimal design with inline editing and value suggestions
 */

import { useState, useRef, useEffect } from 'react';
import { FilterCriterion, ComparisonOperator, AttributeMetadata } from '../types/filters';

interface FilterChipProps {
  filter: FilterCriterion;
  attributeType?: AttributeMetadata['type'];
  onUpdate: (updatedFilter: FilterCriterion) => void;
  onRemove: () => void;
  onEditAttribute: () => void;
  suggestedValues?: Array<string | number>;
}

export default function FilterChip({ filter, attributeType, onUpdate, onRemove, onEditAttribute, suggestedValues = [] }: FilterChipProps) {
  const [editValue, setEditValue] = useState(filter.value ? String(filter.value) : '');
  const [showDropdown, setShowDropdown] = useState(false);
  const [filteredSuggestions, setFilteredSuggestions] = useState(suggestedValues);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Determine if this attribute supports comparison operators (only numeric types)
  const isNumericType = attributeType && ['number', 'object', 'range'].includes(attributeType);

  // Cycle through comparison operators (only for numeric types)
  const cycleOperator = () => {
    if (!isNumericType) return; // Don't allow cycling for non-numeric types

    const operators: ComparisonOperator[] = ['=', '>', '<', '!='];
    const currentIndex = operators.indexOf(filter.operator || '=');
    const nextOp = operators[(currentIndex + 1) % operators.length];
    onUpdate({ ...filter, operator: nextOp });
  };

  // Update filter value on every keystroke for real-time filtering
  const handleValueChange = (newValue: string) => {
    setEditValue(newValue);

    // Filter suggestions based on input
    if (newValue.trim()) {
      const filtered = suggestedValues.filter(val =>
        String(val).toLowerCase().includes(newValue.toLowerCase())
      );
      setFilteredSuggestions(filtered);
      setShowDropdown(filtered.length > 0);

      // Try to parse as number
      const numValue = parseFloat(newValue);
      const finalValue = !isNaN(numValue) ? numValue : newValue.trim();
      onUpdate({ ...filter, value: finalValue });
    } else {
      setFilteredSuggestions(suggestedValues);
      setShowDropdown(false);
      onUpdate({ ...filter, value: undefined });
    }
  };

  // Handle suggestion selection
  const handleSelectSuggestion = (value: string | number) => {
    setEditValue(String(value));
    const numValue = parseFloat(String(value));
    const finalValue = !isNaN(numValue) ? numValue : value;
    onUpdate({ ...filter, value: finalValue });
    setShowDropdown(false);
  };

  // Show dropdown when input is focused
  const handleFocus = () => {
    if (suggestedValues.length > 0) {
      setFilteredSuggestions(suggestedValues);
      setShowDropdown(true);
    }
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="filter-chip-minimal" data-operator={filter.operator || '='}>
      <div className="filter-chip-header">
        <span
          className="filter-attribute"
          onClick={onEditAttribute}
          style={{ cursor: 'pointer' }}
          title="Click to change attribute"
        >
          {filter.displayName}
        </span>
        <button
          className="filter-remove"
          onClick={onRemove}
          title="Remove filter"
        >
          ×
        </button>
      </div>

      <div className="filter-chip-controls">
        {/* Only show operator button for numeric types */}
        {isNumericType && (
          <button
            className="filter-operator"
            data-operator={filter.operator || '='}
            onClick={cycleOperator}
            title="Click to cycle operator: = → > → < → !="
          >
            {filter.operator || '='}
          </button>
        )}

        <div className="filter-input-wrapper">
          <input
            ref={inputRef}
            type="text"
            className="filter-input"
            value={editValue}
            onChange={(e) => handleValueChange(e.target.value)}
            onFocus={handleFocus}
            placeholder="value..."
            autoFocus={!filter.value}
          />

          {showDropdown && filteredSuggestions.length > 0 && (
            <div ref={dropdownRef} className="filter-dropdown">
              {filteredSuggestions.slice(0, 10).map((value, index) => (
                <div
                  key={index}
                  className="filter-dropdown-item"
                  onClick={() => handleSelectSuggestion(value)}
                >
                  {String(value)}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
