/**
 * Dashboard component showing summary statistics
 */

import { useEffect } from 'react';
import { useApp } from '../context/AppContext';

export default function Dashboard() {
  const { summary, categories, loading, error, loadSummary, loadCategories, forceRefresh } = useApp();

  useEffect(() => {
    // Load summary and categories if we don't already have them
    if (!summary) {
      loadSummary();
    }
    if (categories.length === 0) {
      loadCategories();
    }
  }, []);

  if (error) {
    return (
      <div className="error">
        Error: {error}
        <button onClick={loadSummary} style={{ marginLeft: '0.8rem' }}>
          Retry
        </button>
      </div>
    );
  }

  // Show loading only if there's no summary data yet (first load)
  if (loading && !summary && categories.length === 0) {
    return <div className="loading">Loading dashboard...</div>;
  }

  if (!summary && categories.length === 0) {
    return null;
  }

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1 style={{ margin: 0 }}>Dashboard</h1>
        <button
          className="btn-refresh"
          onClick={forceRefresh}
          disabled={loading}
          title="Force refresh data from server (clears cache)"
          style={{
            padding: '0.4rem 0.8rem',
            fontSize: '0.85rem',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.5 : 1,
            border: '1px solid var(--border-color)',
            borderRadius: '4px',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)'
          }}
        >
          ↻ Refresh Data
        </button>
      </div>

      <div className="card" style={{ marginBottom: '1.2rem' }}>
        <h2>About DatasheetMiner</h2>
        <p style={{ color: 'var(--text-secondary)', lineHeight: '1.4' }}>
          Making it easy to size, select, and get moving
        </p>
      </div>

      <div className="stats">
        {/* Total products card (always shown) */}
        {summary && (
          <div className="stat-card">
            <h3>Total Products</h3>
            <div className="value">{summary.total}</div>
          </div>
        )}

        {/* Dynamic category cards */}
        {categories.map((category) => (
          <div key={category.type} className="stat-card">
            <h3>{category.display_name}</h3>
            <div className="value">{category.count}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
