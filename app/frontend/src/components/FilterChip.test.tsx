/**
 * Tests for FilterChip component
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '../test/utils';
import FilterChip from './FilterChip';
import { FilterCriterion } from '../types/filters';

describe('FilterChip', () => {
  const mockFilter: FilterCriterion = {
    attribute: 'manufacturer',
    mode: 'include',
    value: 'ACME',
    displayName: 'Manufacturer',
  };

  const mockUpdate = vi.fn();
  const mockRemove = vi.fn();

  it('should render filter chip with display name', () => {
    render(
      <FilterChip
        filter={mockFilter}
        products={[]}
        suggestedValues={[]}
        onUpdate={mockUpdate}
        onRemove={mockRemove}
        onEditAttribute={vi.fn()}
      />
    );

    expect(screen.getByText(/Manufacturer/i)).toBeInTheDocument();
  });

  it('should show filter value if set', () => {
    render(
      <FilterChip
        filter={mockFilter}
        products={[]}
        suggestedValues={[]}
        onUpdate={mockUpdate}
        onRemove={mockRemove}
        onEditAttribute={vi.fn()}
      />
    );

    const input = screen.getByDisplayValue('ACME');
    expect(input).toBeInTheDocument();
  });

  it('should call onRemove when remove button clicked', () => {
    render(
      <FilterChip
        filter={mockFilter}
        products={[]}
        suggestedValues={[]}
        onUpdate={mockUpdate}
        onRemove={mockRemove}
        onEditAttribute={vi.fn()}
      />
    );

    const removeButton = screen.getByTitle(/Remove/i);
    fireEvent.click(removeButton);

    expect(mockRemove).toHaveBeenCalledTimes(1);
  });

  it('should handle mode changes', () => {
    const { rerender } = render(
      <FilterChip
        filter={mockFilter}
        products={[]}
        suggestedValues={[]}
        onUpdate={mockUpdate}
        onRemove={mockRemove}
        onEditAttribute={vi.fn()}
      />
    );

    const excludeFilter: FilterCriterion = {
      ...mockFilter,
      mode: 'exclude',
    };

    rerender(
      <FilterChip
        filter={excludeFilter}
        products={[]}
        suggestedValues={[]}
        onUpdate={mockUpdate}
        onRemove={mockRemove}
        onEditAttribute={vi.fn()}
      />
    );

    // Should render with different mode
    expect(screen.getByText(/Manufacturer/i)).toBeInTheDocument();
  });

  it('should render without value for new filters', () => {
    const newFilter: FilterCriterion = {
      attribute: 'manufacturer',
      mode: 'include',
      displayName: 'Manufacturer',
    };

    render(
      <FilterChip
        filter={newFilter}
        products={[]}
        suggestedValues={['ACME', 'Beta Corp']}
        onUpdate={mockUpdate}
        onRemove={mockRemove}
        onEditAttribute={vi.fn()}
      />
    );

    expect(screen.getByText(/Manufacturer/i)).toBeInTheDocument();
  });

  describe('multi-select string fields', () => {
    // Two products with distinct part numbers — getAvailableOperators
    // sees only string values for `part_number`, returns ['=', '!='],
    // and the chip switches to multi-select mode.
    const products = [
      { part_number: 'DRV-A1', product_type: 'drive' as const, manufacturer: 'X' },
      { part_number: 'DRV-B2', product_type: 'drive' as const, manufacturer: 'Y' },
      { part_number: 'DRV-C3', product_type: 'drive' as const, manufacturer: 'Z' },
    ] as any;

    const baseFilter: FilterCriterion = {
      attribute: 'part_number',
      mode: 'include',
      displayName: 'Part Number',
      operator: '=',
    };

    it('Enter on a typed value commits it as a new pill (free-form)', () => {
      const onUpdate = vi.fn();
      render(
        <FilterChip
          filter={baseFilter}
          products={products}
          suggestedValues={['DRV-A1', 'DRV-B2', 'DRV-C3']}
          onUpdate={onUpdate}
          onRemove={vi.fn()}
          onEditAttribute={vi.fn()}
        />,
      );

      const input = screen.getByPlaceholderText(/type or pick/i);
      fireEvent.change(input, { target: { value: 'NEW-FREEFORM-VALUE' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      // First commit stores as plain string (not array yet).
      expect(onUpdate).toHaveBeenCalledWith(
        expect.objectContaining({ value: 'NEW-FREEFORM-VALUE' }),
      );
    });

    it('selecting a second suggestion stores both values as an array (OR)', () => {
      const onUpdate = vi.fn();
      const filterWithOne: FilterCriterion = {
        ...baseFilter,
        value: 'DRV-A1',
      };
      render(
        <FilterChip
          filter={filterWithOne}
          products={products}
          suggestedValues={['DRV-A1', 'DRV-B2', 'DRV-C3']}
          onUpdate={onUpdate}
          onRemove={vi.fn()}
          onEditAttribute={vi.fn()}
        />,
      );

      // Open the dropdown by focusing the input.
      const input = screen.getByPlaceholderText(/add another/i);
      fireEvent.focus(input);
      // Type a fragment to commit a second pill via Enter.
      fireEvent.change(input, { target: { value: 'DRV-B2' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      // Second commit upgrades the value to an array — that's what
      // matchesFilter() OR-matches against.
      const lastCall = onUpdate.mock.calls.at(-1)?.[0];
      expect(Array.isArray(lastCall.value)).toBe(true);
      expect(lastCall.value).toEqual(expect.arrayContaining(['DRV-A1', 'DRV-B2']));
    });

    it('Backspace on empty input removes the last pill', () => {
      const onUpdate = vi.fn();
      const filterWithTwo: FilterCriterion = {
        ...baseFilter,
        value: ['DRV-A1', 'DRV-B2'],
      };
      render(
        <FilterChip
          filter={filterWithTwo}
          products={products}
          suggestedValues={['DRV-A1', 'DRV-B2', 'DRV-C3']}
          onUpdate={onUpdate}
          onRemove={vi.fn()}
          onEditAttribute={vi.fn()}
        />,
      );

      const input = screen.getByPlaceholderText(/add another/i);
      // Input is empty; Backspace should peel off the last value.
      fireEvent.keyDown(input, { key: 'Backspace' });

      const lastCall = onUpdate.mock.calls.at(-1)?.[0];
      // One pill left after removal — collapses back to plain string.
      expect(lastCall.value).toBe('DRV-A1');
    });
  });
});
