/**
 * Global application state context
 * Provides shared state across components to avoid page reloads
 */

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Product, ProductSummary, ProductType } from '../types/models';
import { apiClient } from '../api/client';

interface AppState {
  products: Product[];
  summary: ProductSummary | null;
  loading: boolean;
  error: string | null;
}

interface AppContextType extends AppState {
  // Data fetching
  loadProducts: (type?: ProductType) => Promise<void>;
  loadSummary: () => Promise<void>;

  // CRUD operations with optimistic updates
  addProduct: (product: Partial<Product>) => Promise<void>;
  deleteProduct: (id: string, type: ProductType) => Promise<void>;

  // State setters
  setProducts: (products: Product[]) => void;
  setSummary: (summary: ProductSummary) => void;
  setError: (error: string | null) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [summary, setSummary] = useState<ProductSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Cache for product data by type to avoid re-fetching
  const [productCache, setProductCache] = useState<Map<ProductType, Product[]>>(new Map());
  const [currentProductType, setCurrentProductType] = useState<ProductType>('all');

  const loadProducts = useCallback(async (type: ProductType = 'all') => {
    // Check cache first
    const cached = productCache.get(type);
    if (cached && cached.length > 0) {
      setProducts(cached);
      setCurrentProductType(type);
      // Background refresh: fetch new data without blocking UI
      apiClient.listProducts(type).then(data => {
        if (JSON.stringify(data) !== JSON.stringify(cached)) {
          setProducts(data);
          setProductCache(prev => new Map(prev).set(type, data));
        }
      }).catch(() => {
        // Silently fail background refresh, cached data is still valid
      });
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.listProducts(type);
      setProducts(data);

      // Update cache
      setProductCache(prev => new Map(prev).set(type, data));
      setCurrentProductType(type);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load products');
    } finally {
      setLoading(false);
    }
  }, [productCache]);

  const loadSummary = useCallback(async () => {
    // If we already have summary, return it immediately and refresh in background
    if (summary) {
      apiClient.getSummary().then(data => {
        if (JSON.stringify(data) !== JSON.stringify(summary)) {
          setSummary(data);
        }
      }).catch(() => {
        // Silently fail background refresh, cached data is still valid
      });
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getSummary();
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load summary');
    } finally {
      setLoading(false);
    }
  }, [summary]);

  const addProduct = useCallback(async (product: Partial<Product>) => {
    try {
      setLoading(true);
      setError(null);

      // Optimistic update
      const tempId = `temp-${Date.now()}`;
      const optimisticProduct = { ...product, product_id: tempId } as Product;
      setProducts(prev => [...prev, optimisticProduct]);

      // Update summary optimistically
      if (summary && product.product_type) {
        const newSummary = { ...summary, total: summary.total + 1 };
        if (product.product_type === 'motor') {
          newSummary.motors = summary.motors + 1;
        } else if (product.product_type === 'drive') {
          newSummary.drives = summary.drives + 1;
        }
        setSummary(newSummary);
      }

      // Make API call
      await apiClient.createProduct(product);

      // Clear cache and refresh data to get real IDs
      setProductCache(new Map());
      await loadProducts(currentProductType);
      await loadSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add product');
      // Revert optimistic updates
      setProductCache(new Map());
      await loadProducts(currentProductType);
      await loadSummary();
    } finally {
      setLoading(false);
    }
  }, [summary, currentProductType, loadProducts, loadSummary]);

  const deleteProduct = useCallback(async (id: string, type: ProductType) => {
    try {
      setLoading(true);
      setError(null);

      // Optimistic update
      const deletedProduct = products.find(p => p.product_id === id);
      setProducts(prev => prev.filter(p => p.product_id !== id));

      // Update summary optimistically
      if (summary && deletedProduct) {
        const newSummary = { ...summary, total: summary.total - 1 };
        if (deletedProduct.product_type === 'motor') {
          newSummary.motors = summary.motors - 1;
        } else if (deletedProduct.product_type === 'drive') {
          newSummary.drives = summary.drives - 1;
        }
        setSummary(newSummary);
      }

      // Make API call
      await apiClient.deleteProduct(id, type);

      // Clear cache to ensure fresh data on next load
      setProductCache(new Map());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete product');
      // Revert optimistic updates
      setProductCache(new Map());
      await loadProducts(currentProductType);
      await loadSummary();
    } finally {
      setLoading(false);
    }
  }, [products, summary, currentProductType, loadProducts, loadSummary]);

  const value: AppContextType = {
    products,
    summary,
    loading,
    error,
    loadProducts,
    loadSummary,
    addProduct,
    deleteProduct,
    setProducts,
    setSummary,
    setError,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
