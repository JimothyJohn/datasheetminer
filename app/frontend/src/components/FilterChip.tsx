/**
 * Filter chip component with comparison operators
 * Minimal design with inline editing, value suggestions, and sliders for numeric fields
 */

import { useState, useRef, useEffect, useMemo } from 'react';
import { FilterCriterion, AttributeMetadata, getAvailableOperators } from '../types/filters';
import { Product } from '../types/models';

interface FilterChipProps {
  filter: FilterCriterion;
  attributeType?: AttributeMetadata['type'];
  products: Product[];
  onUpdate: (updatedFilter: FilterCriterion) => void;
  onRemove: () => void;
  onEditAttribute: () => void;
  suggestedValues?: Array<string | number>;
  attributeMetadata?: AttributeMetadata;
}

/**
 * Helper function to extract numeric value from nested objects
 */
const getNestedValue = (obj: any, path: string): any => {
  const keys = path.split('.');
  let value = obj;
  for (const key of keys) {
    if (value === undefined || value === null) return undefined;
    value = value[key];
  }
  return value;
};

/**
 * Helper function to extract numeric value from ValueUnit or MinMaxUnit
 */
const extractNumericValue = (value: any): number | null => {
  if (typeof value === 'number') return value;
  if (typeof value === 'object' && value !== null) {
    // ValueUnit: { value: number, unit: string }
    if ('value' in value && typeof value.value === 'number') return value.value;
    // MinMaxUnit: { min: number, max: number, unit: string }
    if ('min' in value && 'max' in value) {
      return (value.min + value.max) / 2;
    }
  }
  return null;
};

/**
 * Get unit string from ValueUnit or MinMaxUnit
 */
const getUnitString = (value: any): string | null => {
  if (typeof value === 'object' && value !== null && 'unit' in value) {
    return value.unit;
  }
  return null;
};

export default function FilterChip({
  filter,
  attributeType,
  products,
  onUpdate,
  onRemove,
  onEditAttribute,
  suggestedValues = [],
  attributeMetadata
}: FilterChipProps) {
  const [editValue, setEditValue] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [filteredSuggestions, setFilteredSuggestions] = useState(suggestedValues);
  const [localSliderValue, setLocalSliderValue] = useState<number>(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Sync local slider value with filter value
  useEffect(() => {
    if (typeof filter.value === 'number') {
      setLocalSliderValue(filter.value);
    } else {
      setLocalSliderValue(0);
    }
  }, [filter.value]);

  // Get available operators based on actual data values
  const availableOperators = useMemo(
    () => getAvailableOperators(products, filter.attribute),
    [products, filter.attribute]
  );

  // Calculate max value for slider (for ValueUnit and MinMaxUnit fields)
  const maxValueInfo = useMemo(() => {
    // Only calculate for 'object' and 'range' types
    if (attributeType !== 'object' && attributeType !== 'range') {
      return null;
    }

    let maxValue = 0;
    let unit: string | null = null;

    products.forEach(product => {
      const value = getNestedValue(product, filter.attribute);
      if (value !== undefined && value !== null) {
        const numValue = extractNumericValue(value);
        if (numValue !== null && numValue > maxValue) {
          maxValue = numValue;
          // Get unit from this value
          if (!unit) {
            unit = getUnitString(value);
          }
        }
      }
    });

    // If we found values, return max with some headroom
    if (maxValue > 0) {
      return {
        max: Math.ceil(maxValue * 1.1), // Add 10% headroom
        unit: unit || attributeMetadata?.unit || ''
      };
    }

    return null;
  }, [products, filter.attribute, attributeType, attributeMetadata]);

  // Determine if we should show a slider (must be stable)
  const showSlider = useMemo(() => {
    // Show slider for 'object' and 'range' types that have numeric values
    return (attributeType === 'object' || attributeType === 'range') && maxValueInfo !== null;
  }, [attributeType, maxValueInfo]);

  // Determine if this is a multi-select string field
  // String fields have only '=' and '!=' operators (or just '=')
  const isMultiSelectField = useMemo(() => {
    return availableOperators.length <= 2 &&
           availableOperators.every(op => op === '=' || op === '!=');
  }, [availableOperators]);

  // Only show operator button if there are multiple operators available AND not multi-select AND not showing slider
  const showOperatorButton = availableOperators.length > 1 && !isMultiSelectField && !showSlider;

  // Get current selected values (as array) - filter out booleans and tuples
  const selectedValues = useMemo(() => {
    if (!filter.value) return [];
    if (Array.isArray(filter.value)) {
      // Filter to only include string | number, not boolean or nested arrays
      return filter.value.filter((v): v is string | number =>
        typeof v === 'string' || typeof v === 'number'
      );
    }
    // Only include if it's string or number
    if (typeof filter.value === 'string' || typeof filter.value === 'number') {
      return [filter.value];
    }
    return [];
  }, [filter.value]);

  // Cycle through comparison operators based on available operators
  const cycleOperator = () => {
    if (availableOperators.length <= 1) return; // Don't allow cycling if only one operator

    const currentIndex = availableOperators.indexOf(filter.operator || '=');
    const nextIndex = currentIndex === -1 ? 0 : (currentIndex + 1) % availableOperators.length;
    const nextOp = availableOperators[nextIndex];
    onUpdate({ ...filter, operator: nextOp });
  };

  // Handle slider value change - update local state only
  const handleSliderChange = (newValue: number) => {
    setLocalSliderValue(newValue);
  };

  // Commit slider value change to parent on drag end
  const handleSliderCommit = () => {
    onUpdate({
      ...filter,
      value: localSliderValue,
      operator: filter.operator || '>=' // Default to >= for slider (minimum value)
    });
  };

  // Update filter value on every keystroke for real-time filtering
  const handleValueChange = (newValue: string) => {
    setEditValue(newValue);

    // Filter suggestions based on input
    if (newValue.trim()) {
      let filtered = suggestedValues.filter(val =>
        String(val).toLowerCase().includes(newValue.toLowerCase())
      );

      // For multi-select, also filter out already selected values
      if (isMultiSelectField) {
        filtered = filtered.filter(val =>
          !selectedValues.map(v => String(v)).includes(String(val))
        );
      }

      setFilteredSuggestions(filtered);
      setShowDropdown(filtered.length > 0);

      // For multi-select fields, don't update immediately - wait for selection
      if (!isMultiSelectField) {
        // Try to parse as number
        const numValue = parseFloat(newValue);
        const finalValue = !isNaN(numValue) ? numValue : newValue.trim();
        onUpdate({ ...filter, value: finalValue });
      }
    } else {
      if (isMultiSelectField) {
        // Show available suggestions (minus already selected)
        const availableSuggestions = suggestedValues.filter(val =>
          !selectedValues.map(v => String(v)).includes(String(val))
        );
        setFilteredSuggestions(availableSuggestions);
        setShowDropdown(false);
      } else {
        setFilteredSuggestions(suggestedValues);
        setShowDropdown(false);
        onUpdate({ ...filter, value: undefined });
      }
    }
  };

  // Handle suggestion selection
  const handleSelectSuggestion = (value: string | number) => {
    if (isMultiSelectField) {
      // Add to array of selected values
      const currentValues = selectedValues.map(v => String(v));
      if (!currentValues.includes(String(value))) {
        const newValues = [...currentValues, String(value)];
        onUpdate({ ...filter, value: newValues.length === 1 ? newValues[0] : newValues });
      }
      setEditValue('');
      setShowDropdown(false);
    } else {
      // Single value - replace existing
      setEditValue(String(value));
      const numValue = parseFloat(String(value));
      const finalValue = !isNaN(numValue) ? numValue : value;
      onUpdate({ ...filter, value: finalValue });
      setShowDropdown(false);
    }
  };

  // Remove a value from multi-select
  const handleRemoveValue = (valueToRemove: string | number) => {
    const currentValues = selectedValues.map(v => String(v));
    const newValues = currentValues.filter(v => v !== String(valueToRemove));

    if (newValues.length === 0) {
      onUpdate({ ...filter, value: undefined });
    } else if (newValues.length === 1) {
      onUpdate({ ...filter, value: newValues[0] });
    } else {
      onUpdate({ ...filter, value: newValues });
    }
  };

  // Show dropdown when input is focused
  const handleFocus = () => {
    if (suggestedValues.length > 0) {
      // For multi-select, filter out already selected values
      if (isMultiSelectField) {
        const availableSuggestions = suggestedValues.filter(val =>
          !selectedValues.map(v => String(v)).includes(String(val))
        );
        setFilteredSuggestions(availableSuggestions);
        setShowDropdown(availableSuggestions.length > 0);
      } else {
        setFilteredSuggestions(suggestedValues);
        setShowDropdown(true);
      }
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

      {/* Show selected values for multi-select fields */}
      {isMultiSelectField && selectedValues.length > 0 && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.25rem',
          marginBottom: '0.3rem',
          padding: '0.2rem 0'
        }}>
          {selectedValues.map((val, idx) => (
            <span
              key={idx}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.3rem',
                padding: '0.15rem 0.35rem',
                background: 'linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%)',
                color: 'white',
                borderRadius: '3px',
                fontSize: '0.75rem',
                fontWeight: 600
              }}
            >
              {String(val)}
              <button
                onClick={() => handleRemoveValue(val)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'white',
                  cursor: 'pointer',
                  padding: 0,
                  fontSize: '0.9rem',
                  lineHeight: 1,
                  opacity: 0.8
                }}
                title="Remove value"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="filter-chip-controls">
        {/* Show operator button if multiple operators available (but not for sliders) */}
        {showOperatorButton && (
          <button
            className="filter-operator"
            data-operator={filter.operator || '='}
            onClick={cycleOperator}
            title={`Click to cycle operator: ${availableOperators.join(' → ')}`}
          >
            {filter.operator || '='}
          </button>
        )}

        {/* Show operator label for sliders (non-interactive) */}
        {showSlider && (
          <span className="filter-operator-label" title="Minimum value filter">
            ≥
          </span>
        )}

        {/* Render slider for numeric ValueUnit/MinMaxUnit fields */}
        {showSlider && maxValueInfo ? (
          <div className="filter-slider-wrapper">
            <input
              type="range"
              className="filter-slider"
              min={0}
              max={maxValueInfo.max}
              step={maxValueInfo.max > 1000 ? 10 : maxValueInfo.max > 100 ? 1 : 0.1}
              value={localSliderValue}
              onChange={(e) => handleSliderChange(parseFloat(e.target.value))}
              onMouseUp={handleSliderCommit}
              onTouchEnd={handleSliderCommit}
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => e.stopPropagation()}
            />
            <div className="filter-slider-value">
              {localSliderValue.toFixed(1)} {maxValueInfo.unit}
            </div>
          </div>
        ) : (
          // Render text input for non-slider fields
          <div className="filter-input-wrapper">
            <input
              ref={inputRef}
              type="text"
              className="filter-input"
              value={editValue}
              onChange={(e) => handleValueChange(e.target.value)}
              onFocus={handleFocus}
              placeholder={isMultiSelectField ? 'add value...' : 'value...'}
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
        )}
      </div>
    </div>
  );
}
