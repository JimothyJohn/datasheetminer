/**
 * Product detail modal that shows full product information
 * Appears at the click location and expands
 */

import { useEffect, useRef } from 'react';
import { Product } from '../types/models';
import { formatPropertyLabel } from '../utils/formatting';

interface ProductDetailModalProps {
  product: Product | null;
  onClose: () => void;
  clickPosition: { x: number; y: number } | null;
}

export default function ProductDetailModal({ product, onClose, clickPosition }: ProductDetailModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!product) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [product, onClose]);

  if (!product || !clickPosition) return null;

  const isNestedObject = (value: any): boolean => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
    // Check if it's a simple value/unit or min/max/unit object
    if (('value' in value && 'unit' in value) || ('min' in value && 'max' in value && 'unit' in value)) {
      return false;
    }
    // It's a nested object like dimensions
    return true;
  };

  const formatValue = (value: any): { display: string; unit?: string } => {
    if (!value) return { display: 'N/A' };

    if (typeof value === 'object' && 'value' in value && 'unit' in value) {
      return { display: String(value.value), unit: value.unit };
    }
    if (typeof value === 'object' && 'min' in value && 'max' in value && 'unit' in value) {
      return { display: `${value.min} - ${value.max}`, unit: value.unit };
    }
    if (Array.isArray(value)) {
      // Check if array contains objects with value/unit
      if (value.length > 0 && typeof value[0] === 'object' && value[0] !== null && 'value' in value[0] && 'unit' in value[0]) {
        const formattedValues = value.map(item => String(item.value)).join(', ');
        const commonUnit = value[0].unit;
        return { display: formattedValues, unit: commonUnit };
      }
      return { display: value.join(', ') };
    }
    return { display: String(value) };
  };

  const renderNestedObject = (value: any) => {
    const entries = Object.entries(value);

    // Check if there's a separate "unit" property at the same level
    const separateUnit = entries.find(([key, _]) => key.toLowerCase() === 'unit');
    const commonUnit = separateUnit ? separateUnit[1] : null;

    // If there's a separate unit property, filter it out from the entries
    const filteredEntries = commonUnit
      ? entries.filter(([key, _]) => key.toLowerCase() !== 'unit')
      : entries;

    // If no separate unit, check if all nested values have the same unit
    let finalUnit = commonUnit;
    if (!finalUnit) {
      const allUnits = filteredEntries
        .map(([_, v]: [string, any]) => {
          if (typeof v === 'object' && v !== null && 'unit' in v) return v.unit;
          return null;
        })
        .filter(Boolean);

      finalUnit = allUnits.length === filteredEntries.length && allUnits.every(u => u === allUnits[0])
        ? allUnits[0]
        : null;
    }

    return (
      <table className="spec-subtable">
        <tbody>
          {filteredEntries.map(([subKey, subValue]: [string, any]) => {
            const formatted = formatValue(subValue);
            const subLabel = formatPropertyLabel(subKey);
            const displayUnit: string = (finalUnit || formatted.unit || '') as string;

            return (
              <tr key={subKey} className="spec-subrow">
                <td className="spec-sublabel">{subLabel}</td>
                <td className="spec-subvalue">{formatted.display}</td>
                <td className="spec-subunit">{displayUnit}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  };

  const groupSpecs = () => {
    const skipKeys = ['product_id', 'product_type', 'PK', 'SK', 'pk', 'sk', 'manufacturer', 'part_number', 'type', 'series', 'datasheet_url'];

    // Define category groups for better organization
    const categories: Record<string, Array<{ key: string; label: string; value: any }>> = {
      'General': [],
      'Electrical': [],
      'Mechanical': [],
      'Performance': [],
      'Physical': [],
      'I/O & Connectivity': [],
      'Safety & Ratings': [],
      'Environmental': [],
      'Other': []
    };

    // Categorization rules
    const categorize = (key: string): string => {
      const electrical = ['voltage', 'current', 'power', 'resistance', 'inductance', 'phases'];
      const mechanical = ['torque', 'speed', 'inertia', 'poles'];
      const performance = ['rated', 'peak', 'constant', 'efficiency'];
      const physical = ['weight', 'dimensions', 'mounting', 'shaft', 'ip_rating'];
      const io = ['inputs', 'outputs', 'ethernet', 'fieldbus', 'encoder', 'feedback', 'control_modes'];
      const safety = ['safety', 'approvals', 'rating'];
      const environmental = ['temp', 'humidity', 'ambient', 'operating'];

      const lowerKey = key.toLowerCase();

      if (electrical.some(e => lowerKey.includes(e))) return 'Electrical';
      if (mechanical.some(m => lowerKey.includes(m))) return 'Mechanical';
      if (performance.some(p => lowerKey.includes(p))) return 'Performance';
      if (physical.some(p => lowerKey.includes(p))) return 'Physical';
      if (io.some(i => lowerKey.includes(i))) return 'I/O & Connectivity';
      if (safety.some(s => lowerKey.includes(s))) return 'Safety & Ratings';
      if (environmental.some(e => lowerKey.includes(e))) return 'Environmental';

      return 'Other';
    };

    Object.entries(product).forEach(([key, value]) => {
      if (skipKeys.includes(key)) return;

      const label = formatPropertyLabel(key);

      const category = categorize(key);
      categories[category].push({ key, label, value });
    });

    // Remove empty categories
    return Object.entries(categories).filter(([_, items]) => items.length > 0);
  };

  const groupedSpecs = groupSpecs();

  return (
    <div className="product-detail-overlay">
      <div
        ref={modalRef}
        className="product-detail-modal"
        style={{
          transformOrigin: `${clickPosition.x}px ${clickPosition.y}px`,
        }}
      >
        <div className="product-detail-header">
          <div>
            <h2>{product.manufacturer || 'Unknown Manufacturer'}</h2>
            {product.datasheet_url && typeof product.datasheet_url === 'object' && 'url' in product.datasheet_url ? (
              <a
                href={(product.datasheet_url as any).url}
                target="_blank"
                rel="noopener noreferrer"
                className="product-detail-part product-detail-part-link"
                title="View datasheet PDF"
                onClick={(e) => e.stopPropagation()}
              >
                {product.part_number || 'N/A'}
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
              </a>
            ) : (
              <p className="product-detail-part">{product.part_number || 'N/A'}</p>
            )}
            {product.type && <p className="product-detail-type">Type: {product.type}</p>}
            {product.series && <p className="product-detail-type">Series: {product.series}</p>}
          </div>
          <button className="product-detail-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="product-detail-content">
          {groupedSpecs.map(([category, items]) => (
            <div key={category} className="spec-category">
              <h3 className="spec-category-title">{category}</h3>
              <table className="spec-table">
                <tbody>
                  {items.map(({ key, label, value }) => {
                    // Check if this is a nested object (like dimensions)
                    if (isNestedObject(value)) {
                      return (
                        <tr key={key} className="spec-row spec-row-nested">
                          <td className="spec-label">{label}</td>
                          <td className="spec-value-nested" colSpan={2}>
                            {renderNestedObject(value)}
                          </td>
                        </tr>
                      );
                    }

                    // Regular value rendering
                    const formatted = formatValue(value);
                    return (
                      <tr key={key} className="spec-row">
                        <td className="spec-label">{label}</td>
                        <td className="spec-value">{formatted.display}</td>
                        {formatted.unit && <td className="spec-unit">{formatted.unit}</td>}
                        {!formatted.unit && <td className="spec-unit"></td>}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
