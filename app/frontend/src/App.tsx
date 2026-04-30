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
import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import ThemeToggle from './components/ThemeToggle';
import GitHubLink from './components/GitHubLink';
import UnitToggle from './components/UnitToggle';
import DensityToggle from './components/DensityToggle';
import NetworkStatus from './components/NetworkStatus';
import ErrorBoundary from './components/ErrorBoundary';
import BuildTray from './components/BuildTray';
import AccountMenu from './components/AccountMenu';
import './App.css';

// ========== App Mode ==========
// public = read-only cloud deployment, admin = local toolset with full access
const APP_MODE = import.meta.env.VITE_APP_MODE || 'admin';
const isAdmin = APP_MODE === 'admin';

// ========== Eager Imports ==========
import ProductList from './components/ProductList';

// ========== Lazy Imports ==========
// Welcome (Specodex landing) — Stage 1 rebrand. Lazy because most users
// land directly on the catalog at "/"; the marketing surface is opt-in.
const Welcome = lazy(() => import('./components/Welcome'));


// ========== Lazy Imports (admin-only, tree-shaken in public builds) ==========
const ProductManagement = isAdmin
  ? lazy(() => import('./components/ProductManagement'))
  : null;

const DatasheetsPage = isAdmin
  ? lazy(() => import('./components/DatasheetsPage'))
  : null;

const AdminPanel = isAdmin
  ? lazy(() => import('./components/AdminPanel'))
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

function AppShell() {
  // The Specodex landing renders its own chrome (OD-green band, footer)
  // and shouldn't sit underneath the existing "Product Search" header.
  const { pathname } = useLocation();
  const isLanding = pathname === '/welcome';
  // The env-var APP_MODE still gates admin component imports (lazy
  // bundles) for now; Cognito group lets a signed-in admin see admin
  // nav on a public deployment in addition to the env-mode case. The
  // full env-mode → group-only swap is Phase 4 in todo/AUTH.md.
  const { isAdmin: authIsAdmin } = useAuth();
  const showAdminNav = isAdmin || authIsAdmin;

  return (
    <>
      {/* ===== NETWORK STATUS INDICATOR ===== */}
      {/* Shows banner when offline (mobile & desktop) */}
      <NetworkStatus />

      <div className="app">
        {!isLanding && (
          <header className="header">
            <div className="header-left">
              <h1>
                <NavLink to="/welcome" className="header-wordmark-link" aria-label="Specodex landing">
                  SPECODEX
                </NavLink>
              </h1>
              <GitHubLink />
              {showAdminNav && (
                <nav className="nav-inline">
                  <NavLink to="/" end className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Selection</NavLink>
                  {DatasheetsPage && <NavLink to="/datasheets" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Datasheets</NavLink>}
                  {ProductManagement && <NavLink to="/management" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Management</NavLink>}
                  {AdminPanel && <NavLink to="/admin" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>Admin</NavLink>}
                </nav>
              )}
            </div>
            <div className="header-options">
              <span className="header-options-label" aria-hidden="true">OPTIONS</span>
              <UnitToggle />
              <DensityToggle />
              <ThemeToggle />
              <AccountMenu />
            </div>
          </header>
        )}

        {/* ===== ROUTES WITH SUSPENSE + ERROR BOUNDARY ===== */}
        <ErrorBoundary>
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              {/* ProductList: Eager loaded (default view, always available) */}
              <Route path="/" element={<ProductList />} />

              {/* Specodex landing (Stage 1 rebrand) */}
              <Route path="/welcome" element={<Welcome />} />

              {/* Admin-only routes (hidden in public mode) */}
              {DatasheetsPage && <Route path="/datasheets" element={<DatasheetsPage />} />}
              {ProductManagement && <Route path="/management" element={<ProductManagement />} />}
              {AdminPanel && <Route path="/admin" element={<AdminPanel />} />}

              {/* Catch-all: Redirect to products */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
        {!isLanding && <BuildTray />}
      </div>
    </>
  );
}

function App() {
  console.log('[App] Rendering application');

  return (
    <AuthProvider>
      <AppProvider>
        <BrowserRouter>
          <AppShell />
        </BrowserRouter>
      </AppProvider>
    </AuthProvider>
  );
}

export default App;
