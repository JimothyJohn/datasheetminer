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
  isOpen,
  anchorElement
}: AttributeSelectorProps & { anchorElement?: HTMLElement | null }) {
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  // Filter attributes based on search
  const filteredAttributes = attributes.filter(attr =>
    attr.displayName.toLowerCase().includes(search.toLowerCase()) ||
    attr.key.toLowerCase().includes(search.toLowerCase())
  );

  // Calculate position when opened
  useEffect(() => {
    if (isOpen && anchorElement) {
      const rect = anchorElement.getBoundingClientRect();
      
      // Default to aligning left edge with anchor left edge, and top with anchor bottom
      // Since overlay is fixed, we use viewport coordinates (rect) directly
      let top = rect.bottom + 8; // 8px gap
      let left = rect.left;
      
      // Check if it would go off screen to the right (rough estimate of width 500px)
      if (left + 500 > window.innerWidth) {
        // Align right edge with anchor right edge
        left = rect.right - 500;
      }
      
      // Check if it would go off screen to the bottom (rough estimate of height 400px)
      if (top + 400 > window.innerHeight) {
        // Position above the button
        top = rect.top - 400 - 8;
      }

      setPosition({ top, left });
    }
  }, [isOpen, anchorElement]);

  // Reset state when opened
  useEffect(() => {
    if (isOpen) {
      setSearch('');
      setSelectedIndex(0);
      // Small timeout to ensure render before focus
      setTimeout(() => {
        inputRef.current?.focus();
      }, 10);
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
      if (isOpen && modalRef.current && !modalRef.current.contains(target) && !anchorElement?.contains(target)) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onClose, anchorElement]);

  if (!isOpen) return null;

  const modalStyle: React.CSSProperties = position ? {
    position: 'absolute',
    top: `${position.top}px`,
    left: `${position.left}px`,
    margin: 0,
    transform: 'none',
    animation: 'none' // Disable slide animation that might conflict
  } : {};

  return (
    <div className="attribute-selector-overlay" style={position ? { 
      background: 'transparent', 
      pointerEvents: 'none', // Let clicks pass through to document for outside click detection
      justifyContent: 'unset',
      alignItems: 'unset',
      padding: 0
    } : {}}>
      <div 
        className="attribute-selector-modal" 
        ref={modalRef}
        style={{
          ...modalStyle,
          pointerEvents: 'auto' // Re-enable pointer events for the modal itself
        }}
      >
        <div className="attribute-selector-header">
          <input
            ref={inputRef}
            type="text"
            className="attribute-selector-input"
            placeholder="Search attributes..."
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
                <div className="attribute-selector-item-content">
                  <span className="attribute-selector-item-name">
                    {attr.displayName}
                  </span>
                  {attr.unit && (
                    <span className="attribute-selector-item-unit">{attr.unit}</span>
                  )}
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
