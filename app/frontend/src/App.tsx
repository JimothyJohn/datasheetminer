/**
 * Main App component with routing
 */

import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import Dashboard from './components/Dashboard';
import ProductList from './components/ProductList';
import ThemeToggle from './components/ThemeToggle';
import './App.css';

function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <div className="app">
          <header className="header">
            <h1>Product Search</h1>
            <ThemeToggle />
          </header>

          <nav className="nav">
            <ul>
              <li>
                <Link to="/">Dashboard</Link>
              </li>
              <li>
                <Link to="/products">Products</Link>
              </li>
            </ul>
          </nav>

          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/products" element={<ProductList />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </AppProvider>
  );
}

export default App;
