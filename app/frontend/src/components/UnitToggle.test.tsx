/**
 * UnitToggle — Phase 4 of FRONTEND_TESTING.md.
 *
 * Locks down the "looks like it worked but didn't" failure mode (L7):
 * the click must flip context state, persist to localStorage, and update
 * the visible label / aria-label all in one action. Exercises both the
 * default 44×44 header chip and the compact sidebar variant.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AppProvider } from '../context/AppContext';
import UnitToggle from './UnitToggle';

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

function renderToggle(props: { compact?: boolean } = {}) {
  return render(
    <AppProvider>
      <UnitToggle {...props} />
    </AppProvider>,
  );
}

describe('UnitToggle (default header chip)', () => {
  it('defaults to SI when localStorage is empty', () => {
    renderToggle();
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('aria-label')).toBe('Switch to imperial units');
    expect(btn.textContent).toContain('SI');
  });

  it('flips to imperial on click and persists', () => {
    renderToggle();
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    expect(btn.getAttribute('aria-label')).toBe('Switch to metric units');
    expect(btn.textContent).toContain('IMP');
    expect(window.localStorage.getItem('unitSystem')).toBe('imperial');
  });

  it('flips back to metric on second click', () => {
    renderToggle();
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(btn.getAttribute('aria-label')).toBe('Switch to imperial units');
    expect(window.localStorage.getItem('unitSystem')).toBe('metric');
  });

  it('hydrates from imperial in localStorage', () => {
    window.localStorage.setItem('unitSystem', 'imperial');
    renderToggle();
    const btn = screen.getByRole('button');
    expect(btn.textContent).toContain('IMP');
    expect(btn.getAttribute('aria-label')).toBe('Switch to metric units');
  });
});

describe('UnitToggle (compact variant)', () => {
  it('renders both SI and IMP pills with the active class on the current one', () => {
    renderToggle({ compact: true });
    const pills = screen.getAllByText(/^(SI|IMP)$/);
    expect(pills).toHaveLength(2);
    const si = pills.find(p => p.textContent === 'SI')!;
    const imp = pills.find(p => p.textContent === 'IMP')!;
    expect(si.className).toContain('active');
    expect(imp.className).not.toContain('active');
  });

  it('moves the active pill from SI to IMP on click', () => {
    renderToggle({ compact: true });
    fireEvent.click(screen.getByRole('button'));
    const pills = screen.getAllByText(/^(SI|IMP)$/);
    const si = pills.find(p => p.textContent === 'SI')!;
    const imp = pills.find(p => p.textContent === 'IMP')!;
    expect(imp.className).toContain('active');
    expect(si.className).not.toContain('active');
  });

  it('renders the UNITS caption (aria-hidden so screen readers skip it)', () => {
    renderToggle({ compact: true });
    const caption = screen.getByText('UNITS');
    expect(caption.getAttribute('aria-hidden')).toBe('true');
  });
});
