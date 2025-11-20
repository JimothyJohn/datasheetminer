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
});
