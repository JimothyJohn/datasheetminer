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
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';

// ========== App Mode ==========
// public = read-only cloud deployment, admin = local toolset with full access
const APP_MODE = import.meta.env.VITE_APP_MODE || 'admin';
const isAdmin = APP_MODE === 'admin';

// ========== Eager Imports ==========
import ProductList from './components/ProductList';
import UploadDatasheet from './components/UploadDatasheet';

// ========== Lazy Imports (public, code-split for smaller initial bundle) ==========
const RecommendationChat = lazy(() => import('./components/RecommendationChat'));

// ========== Lazy Imports (admin-only, tree-shaken in public builds) ==========
const ProductManagement = isAdmin
  ? lazy(() => import('./components/ProductManagement'))
  : null;

const DatasheetsPage = isAdmin
  ? lazy(() => import('./components/DatasheetsPage'))
  : null;

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
                <NavLink to="/" end className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Selection</NavLink>
                <NavLink to="/recommend" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Recommendation</NavLink>
                {isAdmin && <NavLink to="/datasheets" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Datasheets</NavLink>}
                {isAdmin && <NavLink to="/management" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Management</NavLink>}
              </nav>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <UploadDatasheet />
              <ThemeToggle />
            </div>
          </header>

          {/* ===== ROUTES WITH SUSPENSE + ERROR BOUNDARY ===== */}
          <ErrorBoundary>
            <Suspense fallback={<LoadingFallback />}>
              <Routes>
                {/* ProductList: Eager loaded (default view, always available) */}
                <Route path="/" element={<ProductList />} />

                {/* Recommendation: Lazy loaded chat interface */}
                <Route path="/recommend" element={<RecommendationChat />} />

                {/* Admin-only routes (hidden in public mode) */}
                {DatasheetsPage && <Route path="/datasheets" element={<DatasheetsPage />} />}
                {ProductManagement && <Route path="/management" element={<ProductManagement />} />}

                {/* Catch-all: Redirect to products */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </div>
      </BrowserRouter>
    </AppProvider>
  );
}

export default App;
