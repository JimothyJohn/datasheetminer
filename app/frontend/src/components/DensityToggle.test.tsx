/**
 * DensityToggle — Phase 4 of FRONTEND_TESTING.md.
 *
 * The toggle's icon depicts the CURRENT state (3 lines = compact, 2 bars
 * = comfy), and `aria-pressed` reflects "currently compact". Locks down
 * L8 (rowDensity persists + propagates) at the component layer.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AppProvider } from '../context/AppContext';
import DensityToggle from './DensityToggle';

vi.mock('../api/client', () => ({
  apiClient: {
    listProducts: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    getSummary: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    getCategories: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
  },
}));

beforeEach(() => {
  window.localStorage.clear();
});

function renderToggle() {
  return render(
    <AppProvider>
      <DensityToggle />
    </AppProvider>,
  );
}

describe('DensityToggle', () => {
  it('defaults to compact when localStorage is empty', () => {
    renderToggle();
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    expect(btn.getAttribute('aria-label')).toMatch(/compact/i);
  });

  it('flips to comfy on click and persists', () => {
    renderToggle();
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    expect(btn.getAttribute('aria-pressed')).toBe('false');
    expect(btn.getAttribute('aria-label')).toMatch(/comfortable/i);
    expect(window.localStorage.getItem('productListRowDensity')).toBe('comfy');
  });

  it('flips back to compact on second click', () => {
    renderToggle();
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(btn.getAttribute('aria-pressed')).toBe('true');
    expect(window.localStorage.getItem('productListRowDensity')).toBe('compact');
  });

  it('hydrates from comfy in localStorage', () => {
    window.localStorage.setItem('productListRowDensity', 'comfy');
    renderToggle();
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('aria-pressed')).toBe('false');
  });

  it('renders three-line icon when compact, two-bar icon when comfy', () => {
    const { container } = renderToggle();
    expect(container.querySelectorAll('svg rect')).toHaveLength(3);
    fireEvent.click(screen.getByRole('button'));
    expect(container.querySelectorAll('svg rect')).toHaveLength(2);
  });
});
