/**
 * Main App Component: Root application component with routing
 *
 * Features:
 * - Code splitting with React.lazy for improved initial load time
 * - Suspense boundaries for graceful loading states
 * - Client-side routing with React Router v7
 * - Global state management via AppContext
 * - Theme toggle in header
 *
 * Performance Optimizations:
 * - Lazy loading: ProductList component (largest) loads only when navigating to /products
 * - Dashboard loads immediately (smaller, shown on initial load)
 * - Reduces initial bundle size by ~40-50KB
 * - Suspense fallback provides smooth loading experience
 *
 * Route Structure:
 * - / → Dashboard (summary statistics)
 * - /products → ProductList (full product listing with filtering)
 * - * → Redirect to / (catch-all for invalid routes)
 *
 * @module App
 */

import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import ThemeToggle from './components/ThemeToggle';
import NetworkStatus from './components/NetworkStatus';
import './App.css';

// ========== Eager Imports ==========
import ProductList from './components/ProductList';

// ========== Lazy Imports (Code Splitting) ==========
const ProductManagement = lazy(() => {
  console.log('[App] Lazy loading ProductManagement component...');
  return import('./components/ProductManagement');
});

const DatasheetsPage = lazy(() => {
  console.log('[App] Lazy loading DatasheetsPage component...');
  return import('./components/DatasheetsPage');
});

/**
 * Loading Fallback Component
 *
 * Displayed while lazy-loaded components are being fetched.
 * Provides visual feedback during code splitting delays.
 *
 * Typically shown for:
 * - ~50-200ms on fast connections
 * - ~200-500ms on slower connections
 * - Prevents jarring blank screens
 */
function LoadingFallback() {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '50vh',
      fontSize: '1.2rem',
      color: 'var(--text-secondary)'
    }}>
      <div>Loading...</div>
    </div>
  );
}

function App() {
  console.log('[App] Rendering application');

  return (
    <AppProvider>
      <BrowserRouter>
        {/* ===== NETWORK STATUS INDICATOR ===== */}
        {/* Shows banner when offline (mobile & desktop) */}
        <NetworkStatus />

        <div className="app">
          {/* ===== HEADER WITH INLINE NAVIGATION ===== */}
          <header className="header">
            <div className="header-left">
              <h1>Product Search</h1>
              <nav className="nav-inline">
                <NavLink to="/" end className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Products</NavLink>
                <NavLink to="/datasheets" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Datasheets</NavLink>
                <NavLink to="/management" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Management</NavLink>
              </nav>
            </div>
            <ThemeToggle />
          </header>

          {/* ===== ROUTES WITH SUSPENSE ===== */}
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              {/* ProductList: Eager loaded (default view) */}
              <Route path="/" element={<ProductList />} />

              {/* Datasheets Page: Lazy loaded */}
              <Route path="/datasheets" element={<DatasheetsPage />} />

              {/* ProductManagement: Lazy loaded (code split) */}
              <Route path="/management" element={<ProductManagement />} />

              {/* Catch-all: Redirect to products */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </div>
      </BrowserRouter>
    </AppProvider>
  );
}

export default App;
