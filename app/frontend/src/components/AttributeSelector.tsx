/**
 * Searchable attribute selector with keyboard navigation
 * Similar to ChatGPT-style command palette
 */

import { useState, useEffect, useRef, KeyboardEvent } from 'react';
import { AttributeMetadata } from '../types/filters';

interface AttributeSelectorProps {
  attributes: AttributeMetadata[];
  onSelect: (attribute: AttributeMetadata) => void;
  onClose: () => void;
  isOpen: boolean;
}

export default function AttributeSelector({
  attributes,
  onSelect,
  onClose,
  isOpen
}: AttributeSelectorProps) {
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Filter attributes based on search
  const filteredAttributes = attributes.filter(attr =>
    attr.displayName.toLowerCase().includes(search.toLowerCase()) ||
    attr.key.toLowerCase().includes(search.toLowerCase())
  );

  // Reset state when opened
  useEffect(() => {
    if (isOpen) {
      setSearch('');
      setSelectedIndex(0);
      inputRef.current?.focus();
    }
  }, [isOpen]);

  // Keep selected item in view
  useEffect(() => {
    if (listRef.current) {
      const selectedElement = listRef.current.children[selectedIndex] as HTMLElement;
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex]);

  // Handle keyboard navigation
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev =>
          prev < filteredAttributes.length - 1 ? prev + 1 : prev
        );
        break;

      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => prev > 0 ? prev - 1 : 0);
        break;

      case 'Enter':
        e.preventDefault();
        if (filteredAttributes[selectedIndex]) {
          onSelect(filteredAttributes[selectedIndex]);
          onClose();
        }
        break;

      case 'Escape':
        e.preventDefault();
        onClose();
        break;
    }
  };

  // Handle click outside to close
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (isOpen && !target.closest('.attribute-selector-modal')) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="attribute-selector-overlay">
      <div className="attribute-selector-modal">
        <div className="attribute-selector-header">
          <input
            ref={inputRef}
            type="text"
            className="attribute-selector-input"
            placeholder="Search attributes... (type to filter, ↑↓ to navigate, Enter to select)"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
          />
          <button
            className="attribute-selector-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="attribute-selector-list" ref={listRef}>
          {filteredAttributes.length === 0 ? (
            <div className="attribute-selector-empty">
              No attributes found matching "{search}"
            </div>
          ) : (
            filteredAttributes.map((attr, index) => (
              <div
                key={attr.key}
                className={`attribute-selector-item ${
                  index === selectedIndex ? 'selected' : ''
                }`}
                onClick={() => {
                  onSelect(attr);
                  onClose();
                }}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                <div className="attribute-selector-item-name">
                  {attr.displayName}
                </div>
                <div className="attribute-selector-item-meta">
                  <span className="attribute-selector-item-key">{attr.key}</span>
                  <span className="attribute-selector-item-type">{attr.type}</span>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="attribute-selector-footer">
          {filteredAttributes.length} attribute{filteredAttributes.length !== 1 ? 's' : ''} available
        </div>
      </div>
    </div>
  );
}
