/**
 * Dashboard component showing summary statistics
 */

import { useEffect } from 'react';
import { useApp } from '../context/AppContext';

export default function Dashboard() {
  const { summary, loading, error, loadSummary } = useApp();

  useEffect(() => {
    // Only load if we don't already have summary data
    if (!summary) {
      loadSummary();
    }
  }, []);

  if (error) {
    return (
      <div className="error">
        Error: {error}
        <button onClick={loadSummary} style={{ marginLeft: '1rem' }}>
          Retry
        </button>
      </div>
    );
  }

  // Show loading only if there's no summary data yet (first load)
  if (loading && !summary) {
    return <div className="loading">Loading summary...</div>;
  }

  if (!summary) {
    return null;
  }

  return (
    <div className="container">
      <h1 style={{ marginBottom: '1.5rem' }}>Dashboard</h1>

      <div className="stats">
        <div className="stat-card">
          <h3>Total Products</h3>
          <div className="value">{summary.total}</div>
        </div>

        <div className="stat-card">
          <h3>Motors</h3>
          <div className="value">{summary.motors}</div>
        </div>

        <div className="stat-card">
          <h3>Drives</h3>
          <div className="value">{summary.drives}</div>
        </div>
      </div>

      <div className="card">
        <h2>About DatasheetMiner</h2>
        <p style={{ color: '#666', lineHeight: '1.6' }}>
          DatasheetMiner is a web application for viewing and managing product datasheets.
          Browse motors and drives, view detailed specifications, and manage your product
          database all from this interface.
        </p>
      </div>
    </div>
  );
}
