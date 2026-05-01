/**
 * Route smoke render — Phase 8 of FRONTEND_TESTING.md.
 *
 * Renders <AppShell /> wrapped in MemoryRouter for each registered route
 * and asserts:
 *   1. Some recognizable, route-specific element appears in the DOM.
 *   2. The ErrorBoundary fallback ("Something went wrong") is NOT shown.
 *   3. No throw bubbles past Suspense + ErrorBoundary.
 *
 * One file, five routes — catches "I broke an import" or "I renamed a
 * lazy-loaded module" before CI does. Heavier than the helper-level
 * tests, lighter than a full browser harness; the goal is to make
 * import-time + initial-render regressions impossible to ship silently.
 *
 * apiClient is mocked at module level so any incidental data fetch
 * triggered by AppContext or a route's mount effect rejects loudly
 * instead of attempting a JSDOM network call.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AppProvider } from '../context/AppContext';
import { AppShell } from '../App';

vi.mock('../api/client', () => ({
  apiClient: {
    listProducts: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    getSummary: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    getCategories: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    createProduct: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    updateProduct: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    deleteProduct: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    listDatasheets: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    createDatasheet: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    updateDatasheet: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
    deleteDatasheet: vi.fn(() => Promise.reject(new Error('apiClient not available in unit test'))),
  },
  default: {},
}));

function renderRoute(path: string) {
  return render(
    <AppProvider>
      <MemoryRouter initialEntries={[path]}>
        <AppShell />
      </MemoryRouter>
    </AppProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

describe('AppShell smoke render', () => {
  it('renders / (ProductList) without hitting the ErrorBoundary fallback', async () => {
    renderRoute('/');
    // Categories are empty (mocked apiClient never resolves), so the
    // FilterBar's product-type dropdown sits at "Loading...".
    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
    expect(screen.queryByText(/something went wrong/i)).toBeNull();
  });

  it('renders /welcome (lazy-loaded landing) with the hero copy', async () => {
    renderRoute('/welcome');
    await waitFor(() => {
      expect(screen.getByText(/A product selection frontend/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/something went wrong/i)).toBeNull();
  });

  it('renders /datasheets (lazy, admin-only)', async () => {
    renderRoute('/datasheets');
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /datasheets/i, level: 1 })).toBeInTheDocument();
    });
    expect(screen.queryByText(/something went wrong/i)).toBeNull();
  });

  it('renders /management (lazy, admin-only)', async () => {
    renderRoute('/management');
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /product management/i, level: 2 })).toBeInTheDocument();
    });
    expect(screen.queryByText(/something went wrong/i)).toBeNull();
  });

  it('renders /admin (lazy, admin-only)', async () => {
    renderRoute('/admin');
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^admin$/i, level: 2 })).toBeInTheDocument();
    });
    expect(screen.queryByText(/something went wrong/i)).toBeNull();
  });

  it('redirects an unknown route back to / (ProductList catch-all)', async () => {
    renderRoute('/this-route-does-not-exist');
    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
    expect(screen.queryByText(/something went wrong/i)).toBeNull();
  });
});
