/**
 * Tests for AttributeSelector component
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '../test/utils';
import AttributeSelector from './AttributeSelector';
import { AttributeMetadata } from '../types/filters';

describe('AttributeSelector', () => {
  const mockAttributes: AttributeMetadata[] = [
    {
      key: 'manufacturer',
      displayName: 'Manufacturer',
      type: 'string',
      applicableTypes: ['motor', 'drive'],
    },
    {
      key: 'rated_power',
      displayName: 'Rated Power',
      type: 'object',
      applicableTypes: ['motor'],
      nested: true,
    },
    {
      key: 'part_number',
      displayName: 'Part Number',
      type: 'string',
      applicableTypes: ['motor', 'drive'],
    },
  ];

  const mockSelect = vi.fn();
  const mockClose = vi.fn();

  it('should not render when closed', () => {
    render(
      <AttributeSelector
        attributes={mockAttributes}
        onSelect={mockSelect}
        onClose={mockClose}
        isOpen={false}
      />
    );

    expect(screen.queryByText(/Select Attribute/i)).not.toBeInTheDocument();
  });

  it('should render when open', () => {
    render(
      <AttributeSelector
        attributes={mockAttributes}
        onSelect={mockSelect}
        onClose={mockClose}
        isOpen={true}
      />
    );

    expect(screen.getByPlaceholderText(/Search attributes/i)).toBeInTheDocument();
  });

  it('should display all attributes', () => {
    render(
      <AttributeSelector
        attributes={mockAttributes}
        onSelect={mockSelect}
        onClose={mockClose}
        isOpen={true}
      />
    );

    expect(screen.getByText('Manufacturer')).toBeInTheDocument();
    expect(screen.getByText('Rated Power')).toBeInTheDocument();
    expect(screen.getByText('Part Number')).toBeInTheDocument();
  });

  it('should call onSelect when attribute clicked', () => {
    render(
      <AttributeSelector
        attributes={mockAttributes}
        onSelect={mockSelect}
        onClose={mockClose}
        isOpen={true}
      />
    );

    const manufacturerButton = screen.getByText('Manufacturer');
    fireEvent.click(manufacturerButton);

    expect(mockSelect).toHaveBeenCalledWith(mockAttributes[0]);
  });

  it('should call onClose when overlay clicked', () => {
    render(
      <AttributeSelector
        attributes={mockAttributes}
        onSelect={mockSelect}
        onClose={mockClose}
        isOpen={true}
      />
    );

    const overlay = document.querySelector('.modal-overlay');
    if (overlay) {
      fireEvent.click(overlay);
      expect(mockClose).toHaveBeenCalled();
    }
  });

  it('should filter attributes by search', () => {
    render(
      <AttributeSelector
        attributes={mockAttributes}
        onSelect={mockSelect}
        onClose={mockClose}
        isOpen={true}
      />
    );

    const searchInput = screen.getByPlaceholderText(/Search/i);
    fireEvent.change(searchInput, { target: { value: 'power' } });

    expect(screen.getByText('Rated Power')).toBeInTheDocument();
    expect(screen.queryByText('Manufacturer')).not.toBeInTheDocument();
  });

  it('should handle empty attributes list', () => {
    render(
      <AttributeSelector
        attributes={[]}
        onSelect={mockSelect}
        onClose={mockClose}
        isOpen={true}
      />
    );

    expect(screen.getByText(/No attributes found matching/i)).toBeInTheDocument();
  });
});
