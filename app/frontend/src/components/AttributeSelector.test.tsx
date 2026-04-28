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

    expect(screen.getByPlaceholderText(/Search specs/i)).toBeInTheDocument();
  });

  it('should display attributes from expanded sections, hide collapsed ones', () => {
    render(
      <AttributeSelector
        attributes={mockAttributes}
        onSelect={mockSelect}
        onClose={mockClose}
        isOpen={true}
      />
    );

    // Mechanical is expanded by default — Rated Power renders immediately.
    expect(screen.getByText('Rated Power')).toBeInTheDocument();
    // Identification is collapsed by default — its items aren't in the DOM
    // until the header is clicked.
    expect(screen.queryByText('Manufacturer')).not.toBeInTheDocument();
    expect(screen.queryByText('Part Number')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Identification'));

    expect(screen.getByText('Manufacturer')).toBeInTheDocument();
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

    // Rated Power is in `mechanical` (expanded by default) so it's directly
    // clickable without needing to expand its section first.
    const ratedPowerButton = screen.getByText('Rated Power');
    fireEvent.click(ratedPowerButton);

    expect(mockSelect).toHaveBeenCalledWith(mockAttributes[1]);
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

  it('should show fallback hint when attributes list is empty', () => {
    render(
      <AttributeSelector
        attributes={[]}
        onSelect={mockSelect}
        onClose={mockClose}
        isOpen={true}
      />
    );

    expect(screen.getByText(/No specs available/i)).toBeInTheDocument();
  });

  it('should render the supplied emptyHint when attributes list is empty', () => {
    render(
      <AttributeSelector
        attributes={[]}
        onSelect={mockSelect}
        onClose={mockClose}
        isOpen={true}
        emptyHint={<span>Pick a product type first</span>}
      />
    );

    expect(screen.getByText(/Pick a product type first/i)).toBeInTheDocument();
  });
});
