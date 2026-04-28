/**
 * Searchable attribute selector with keyboard navigation
 * Similar to ChatGPT-style command palette
 */

import { Fragment, ReactNode, useState, useEffect, useRef, KeyboardEvent, useMemo } from 'react';
import {
  AttributeMetadata,
  AttributeCategory,
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  DEFAULT_EXPANDED_CATEGORIES,
  getCategoryForKey,
} from '../types/filters';

interface AttributeSelectorProps {
  attributes: AttributeMetadata[];
  onSelect: (attribute: AttributeMetadata) => void;
  onClose: () => void;
  isOpen: boolean;
  // Custom message rendered when `attributes` is empty. Lets the caller
  // explain *why* (e.g. "select a product type first") instead of dropping
  // the user into a search box over nothing. When omitted, the modal
  // shows a generic empty state.
  emptyHint?: ReactNode;
}

export default function AttributeSelector({
  attributes,
  onSelect,
  onClose,
  isOpen,
  emptyHint,
  anchorElement,
  cursorPosition,
}: AttributeSelectorProps & {
  anchorElement?: HTMLElement | null;
  cursorPosition?: { x: number; y: number } | null;
}) {
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [expanded, setExpanded] = useState<Set<AttributeCategory>>(
    () => new Set(DEFAULT_EXPANDED_CATEGORIES)
  );
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  // Filter attributes based on search, then re-sort into category-section
  // order so the on-screen list reads top-to-bottom as Mechanical →
  // Electrical → Environment → Software → Network → Identification → Other.
  // Within a section the original (curated) order is preserved by the
  // stable sort, so per-type tuning in `getXxxAttributes()` still wins.
  const filteredAttributes = useMemo(() => {
    const matches = attributes.filter(attr =>
      attr.displayName.toLowerCase().includes(search.toLowerCase()) ||
      attr.key.toLowerCase().includes(search.toLowerCase())
    );
    const rank = new Map(CATEGORY_ORDER.map((c, i) => [c, i] as const));
    return [...matches].sort((a, b) => {
      const ra = rank.get(getCategoryForKey(a.key)) ?? CATEGORY_ORDER.length;
      const rb = rank.get(getCategoryForKey(b.key)) ?? CATEGORY_ORDER.length;
      return ra - rb;
    });
  }, [attributes, search]);

  // Active search auto-expands every section so matches never hide behind
  // a collapsed header. The user's saved expand-state is preserved and
  // takes effect again the moment the input is cleared. Header click
  // always toggles the saved state regardless of search.
  const isCategoryOpen = (category: AttributeCategory) =>
    search.length > 0 || expanded.has(category);

  // Group displayed attributes by category, marking each group with whether
  // its body should render. Items in collapsed sections aren't included in
  // the flat keyboard-nav list — selectedIndex only sees what's visible.
  const groupedAttributes = useMemo(() => {
    const groups: {
      category: AttributeCategory;
      items: AttributeMetadata[];
      open: boolean;
    }[] = [];
    let current: typeof groups[number] | null = null;
    for (const attr of filteredAttributes) {
      const category = getCategoryForKey(attr.key);
      if (!current || current.category !== category) {
        current = { category, items: [], open: isCategoryOpen(category) };
        groups.push(current);
      }
      current.items.push(attr);
    }
    return groups;
    // isCategoryOpen depends on search + expanded — list both so React
    // re-derives groups when either changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filteredAttributes, search, expanded]);

  // Flat list of items the user can actually navigate (everything in an
  // open section). selectedIndex is an index into this array.
  const visibleAttributes = useMemo(
    () => groupedAttributes.flatMap(g => (g.open ? g.items : [])),
    [groupedAttributes],
  );

  const toggleCategory = (category: AttributeCategory) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
    // Reset selection — toggling shifts which items are visible, so the
    // previous selectedIndex would point at the wrong item or out of range.
    setSelectedIndex(0);
  };

  // Calculate position when opened.
  // Priority: cursor position (drop-at-cursor — search bar lands under the
  // pointer so the top result is one mouse-flick away) > anchor element
  // (legacy below-the-button behavior) > centered overlay (fallback).
  useEffect(() => {
    if (!isOpen) return;

    const MODAL_WIDTH = 260;
    const MODAL_MAX_HEIGHT = Math.min(window.innerHeight * 0.5, 360);
    const PAD = 8;

    if (cursorPosition) {
      // Place the search-bar row right under the cursor — header is the
      // first thing rendered, so the pointer doesn't have to traverse the
      // modal to reach it. A small offset keeps the click target visible.
      let left = cursorPosition.x - 12;
      let top = cursorPosition.y - 10;

      if (left + MODAL_WIDTH > window.innerWidth - PAD) {
        left = window.innerWidth - MODAL_WIDTH - PAD;
      }
      if (left < PAD) left = PAD;

      if (top + MODAL_MAX_HEIGHT > window.innerHeight - PAD) {
        top = Math.max(PAD, window.innerHeight - MODAL_MAX_HEIGHT - PAD);
      }
      if (top < PAD) top = PAD;

      setPosition({ top, left });
      return;
    }

    if (anchorElement) {
      const rect = anchorElement.getBoundingClientRect();

      let top = rect.bottom + 4;
      let left = rect.right - MODAL_WIDTH;

      if (left < PAD) left = PAD;
      if (top + MODAL_MAX_HEIGHT > window.innerHeight - PAD) {
        top = Math.max(PAD, rect.top - MODAL_MAX_HEIGHT - 4);
      }

      setPosition({ top, left });
      return;
    }

    setPosition(null);
  }, [isOpen, anchorElement, cursorPosition]);

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

  // Keep selected item in view. Section headers are interleaved as
  // siblings with a different className, so query for items only —
  // the Nth match corresponds to filteredAttributes[selectedIndex].
  useEffect(() => {
    if (listRef.current) {
      const items = listRef.current.querySelectorAll<HTMLElement>('.attribute-selector-item');
      const selectedElement = items[selectedIndex];
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex]);

  // Handle keyboard navigation. Indexes into `visibleAttributes` —
  // items in collapsed sections are skipped entirely.
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev =>
          prev < visibleAttributes.length - 1 ? prev + 1 : prev
        );
        break;

      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => prev > 0 ? prev - 1 : 0);
        break;

      case 'Enter':
        e.preventDefault();
        if (visibleAttributes[selectedIndex]) {
          onSelect(visibleAttributes[selectedIndex]);
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
    animation: 'none'
  } : {};

  return (
    <div className="attribute-selector-overlay" style={position ? {
      background: 'transparent',
      pointerEvents: 'none',
      justifyContent: 'unset',
      alignItems: 'unset',
      padding: 0
    } : {}}>
      <div
        className="attribute-selector-modal"
        ref={modalRef}
        style={{
          ...modalStyle,
          pointerEvents: 'auto'
        }}
      >
        <div className="attribute-selector-header">
          {attributes.length > 0 ? (
            <input
              ref={inputRef}
              type="text"
              className="attribute-selector-input"
              placeholder="Search specs..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSelectedIndex(0);
              }}
              onKeyDown={handleKeyDown}
            />
          ) : (
            <div className="attribute-selector-input-placeholder" aria-hidden="true">
              Search specs…
            </div>
          )}
          <button
            className="attribute-selector-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="attribute-selector-list" ref={listRef}>
          {attributes.length === 0 ? (
            <div className="attribute-selector-hint" role="status">
              {emptyHint ?? 'No specs available.'}
            </div>
          ) : filteredAttributes.length === 0 ? (
            <div className="attribute-selector-empty">
              No specs found matching "{search}"
            </div>
          ) : (
            (() => {
              let flatIndex = 0;
              return groupedAttributes.map(({ category, items, open }) => (
                <Fragment key={category}>
                  <button
                    type="button"
                    className="attribute-selector-section-header"
                    onClick={() => toggleCategory(category)}
                    aria-expanded={open}
                  >
                    <span
                      className="attribute-selector-section-chevron"
                      aria-hidden="true"
                    >
                      {open ? '▼' : '▶'}
                    </span>
                    <span className="attribute-selector-section-label">
                      {CATEGORY_LABELS[category]}
                    </span>
                    <span className="attribute-selector-section-count">
                      {items.length}
                    </span>
                  </button>
                  {open && items.map((attr) => {
                    const index = flatIndex++;
                    return (
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
                    );
                  })}
                </Fragment>
              ));
            })()
          )}
        </div>

        {attributes.length > 0 && (
          <div className="attribute-selector-footer">
            {filteredAttributes.length} spec{filteredAttributes.length !== 1 ? 's' : ''} available
          </div>
        )}
      </div>
    </div>
  );
}
