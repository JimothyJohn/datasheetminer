/**
 * AppContext: Global Application State Management
 *
 * This context provides centralized state management for the entire application,
 * implementing optimistic updates, intelligent caching, and background data refresh
 * to create a snappy, responsive user experience.
 *
 * Key Features:
 * - Optimistic UI updates: UI responds immediately before API confirmation
 * - Smart caching: Avoids redundant API calls with Map-based cache per product type
 * - Background refresh: Updates cached data silently without blocking the UI
 * - Error recovery: Automatically reverts optimistic updates on failure
 * - Type safety: Full TypeScript support with strict typing
 *
 * Architecture Pattern: Context API + Custom Hooks (no Redux/Zustand needed)
 *
 * @module AppContext
 */

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Product, ProductSummary, ProductType } from '../types/models';
import { apiClient } from '../api/client';

/**
 * Product category interface
 * Represents a unique product type with count and display name
 */
export interface ProductCategory {
  type: string;          // Internal type name (e.g., 'motor', 'robot_arm')
  count: number;         // Number of products of this type
  display_name: string;  // Human-readable name (e.g., 'Motors', 'Robot Arms')
}

/**
 * Core application state interface
 * Contains the minimal state needed for the entire app
 */
interface AppState {
  products: Product[];        // Currently displayed products
  summary: ProductSummary | null;  // Aggregated product statistics
  categories: ProductCategory[];    // All unique product categories with counts
  loading: boolean;           // Global loading indicator
  error: string | null;       // Latest error message (null if no error)
}

/**
 * Extended context interface with methods
 * Provides both state and state manipulation functions
 */
interface AppContextType extends AppState {
  // Data fetching operations
  loadProducts: (type?: ProductType) => Promise<void>;  // Fetch products with caching
  loadSummary: () => Promise<void>;                     // Fetch summary statistics
  loadCategories: () => Promise<void>;                  // Fetch all product categories
  forceRefresh: () => Promise<void>;                    // Clear cache and force refresh

  // CRUD operations with optimistic updates for better UX
  addProduct: (product: Partial<Product>) => Promise<void>;      // Create new product
  deleteProduct: (id: string, type: Exclude<ProductType, null>) => Promise<void>; // Delete existing product

  // Direct state setters (used sparingly, prefer methods above)
  setProducts: (products: Product[]) => void;
  setSummary: (summary: ProductSummary) => void;
  setCategories: (categories: ProductCategory[]) => void;
  setError: (error: string | null) => void;
}

/**
 * React Context instance
 * Initialized as undefined to enforce usage within AppProvider
 */
const AppContext = createContext<AppContextType | undefined>(undefined);

/**
 * AppProvider Component
 *
 * Wraps the application tree and provides global state to all children.
 * This should be placed at the root level in main.tsx.
 *
 * @param children - React components to wrap with context
 */
export function AppProvider({ children }: { children: ReactNode }) {
  // ========== Core State ==========
  const [products, setProducts] = useState<Product[]>([]);
  const [summary, setSummary] = useState<ProductSummary | null>(null);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ========== Caching Infrastructure ==========
  /**
   * Product cache: Map<ProductType, Product[]>
   * Stores fetched products by type to avoid redundant API calls
   * Example: { 'motor': [...], 'drive': [...], 'all': [...] }
   */
  const [productCache, setProductCache] = useState<Map<ProductType, Product[]>>(new Map());

  /**
   * Current product type being displayed
   * Used to determine which cache to invalidate on mutations
   */
  const [currentProductType, setCurrentProductType] = useState<ProductType>(null);

  // ========== Data Loading Methods ==========

  /**
   * Load products with intelligent caching and background refresh
   *
   * Strategy:
   * 1. If cache exists → show cached data immediately (instant UI)
   * 2. Then fetch fresh data in background without blocking
   * 3. If fresh data differs → update UI silently
   * 4. If no cache → show loading state and fetch data
   *
   * This provides instant feedback while ensuring data freshness.
   *
   * @param type - Product type filter ('motor', 'drive', 'all', or null)
   * @returns Promise that resolves when initial load completes (cache or API)
   *
   * Performance: ~0ms with cache, ~200-500ms without cache
   */
  const loadProducts = useCallback(async (type: ProductType = 'all') => {
    console.log(`[AppContext] loadProducts called with type: ${type}`);

    // Don't load if type is null (no selection)
    if (type === null) {
      console.log(`[AppContext] Skipping loadProducts - no product type selected`);
      setProducts([]);
      setCurrentProductType(null);
      return;
    }

    // ===== CACHE CHECK =====
    const cached = productCache.get(type);
    if (cached && cached.length > 0) {
      console.log(`[AppContext] Cache HIT for ${type}, found ${cached.length} products`);

      // Immediately show cached data (instant UI response)
      setProducts(cached);
      setCurrentProductType(type);

      // ===== BACKGROUND REFRESH =====
      // Fetch fresh data without blocking the UI or showing loading states
      console.log(`[AppContext] Starting background refresh for ${type}`);
      apiClient.listProducts(type).then(data => {
        // Only update if data actually changed (prevents unnecessary re-renders)
        if (JSON.stringify(data) !== JSON.stringify(cached)) {
          console.log(`[AppContext] Background refresh found ${data.length} products (changed from cache)`);
          setProducts(data);
          setProductCache(prev => new Map(prev).set(type, data));
        } else {
          console.log(`[AppContext] Background refresh complete, data unchanged`);
        }
      }).catch((err) => {
        // Silently fail background refresh - cached data is still valid
        console.warn(`[AppContext] Background refresh failed (non-critical):`, err);
      });

      return; // Exit early - we're done (background refresh continues async)
    }

    // ===== CACHE MISS =====
    console.log(`[AppContext] Cache MISS for ${type}, fetching from API`);

    try {
      setLoading(true);  // Show loading indicator
      setError(null);     // Clear any previous errors

      const data = await apiClient.listProducts(type);
      console.log(`[AppContext] API returned ${data.length} products for ${type}`);

      setProducts(data);

      // ===== UPDATE CACHE =====
      // Store fetched data for future instant retrieval
      setProductCache(prev => new Map(prev).set(type, data));
      setCurrentProductType(type);

    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to load products';
      console.error(`[AppContext] Failed to load products:`, err);
      setError(errorMsg);

    } finally {
      setLoading(false);
    }
  }, [productCache]);

  /**
   * Load product summary statistics with caching
   *
   * Strategy similar to loadProducts:
   * 1. If summary exists → return immediately + background refresh
   * 2. If no summary → show loading + fetch from API
   *
   * Summary includes: { total: number, motors: number, drives: number }
   *
   * @returns Promise that resolves when initial load completes
   *
   * Performance: ~0ms with cache, ~100-300ms without cache
   */
  const loadSummary = useCallback(async () => {
    console.log('[AppContext] loadSummary called');

    // ===== CACHE CHECK =====
    if (summary) {
      console.log('[AppContext] Summary cache HIT:', summary);

      // ===== BACKGROUND REFRESH =====
      console.log('[AppContext] Starting background refresh for summary');
      apiClient.getSummary().then(data => {
        // Only update if data changed
        if (JSON.stringify(data) !== JSON.stringify(summary)) {
          console.log('[AppContext] Summary changed:', data);
          setSummary(data);
        } else {
          console.log('[AppContext] Summary unchanged');
        }
      }).catch((err) => {
        // Silently fail - cached summary is still valid
        console.warn('[AppContext] Summary background refresh failed (non-critical):', err);
      });

      return; // Exit early
    }

    // ===== CACHE MISS =====
    console.log('[AppContext] Summary cache MISS, fetching from API');

    try {
      setLoading(true);
      setError(null);

      const data = await apiClient.getSummary();
      console.log('[AppContext] Summary API response:', data);
      setSummary(data);

    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to load summary';
      console.error('[AppContext] Failed to load summary:', err);
      setError(errorMsg);

    } finally {
      setLoading(false);
    }
  }, [summary]);

  /**
   * Load all product categories with intelligent caching
   *
   * Fetches all unique product types that exist in the database.
   * This is used to dynamically populate category selectors without
   * hardcoding product types.
   *
   * Strategy:
   * 1. If categories exist → return immediately + background refresh
   * 2. If no categories → show loading + fetch from API
   *
   * @returns Promise that resolves when initial load completes
   *
   * Performance: ~0ms with cache, ~100-300ms without cache
   */
  const loadCategories = useCallback(async () => {
    console.log('[AppContext] loadCategories called');

    // ===== CACHE CHECK =====
    if (categories.length > 0) {
      console.log(`[AppContext] Categories cache HIT: ${categories.length} categories`);

      // ===== BACKGROUND REFRESH =====
      console.log('[AppContext] Starting background refresh for categories');
      apiClient.getCategories().then(data => {
        // Only update if data changed
        if (JSON.stringify(data) !== JSON.stringify(categories)) {
          console.log(`[AppContext] Categories changed: ${data.length} categories`);
          setCategories(data);
        } else {
          console.log('[AppContext] Categories unchanged');
        }
      }).catch((err) => {
        // Silently fail - cached categories still valid
        console.warn('[AppContext] Categories background refresh failed (non-critical):', err);
      });

      return; // Exit early
    }

    // ===== CACHE MISS =====
    console.log('[AppContext] Categories cache MISS, fetching from API');

    try {
      setLoading(true);
      setError(null);

      const data = await apiClient.getCategories();
      console.log(`[AppContext] Categories API response: ${data.length} categories`, data);
      setCategories(data);

    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to load categories';
      console.error('[AppContext] Failed to load categories:', err);
      setError(errorMsg);

    } finally {
      setLoading(false);
    }
  }, [categories]);

  // ========== CRUD Operations with Optimistic Updates ==========

  /**
   * Add a new product with optimistic UI update
   *
   * Optimistic Update Pattern:
   * 1. Immediately add product to UI with temporary ID (instant feedback)
   * 2. Update summary statistics optimistically
   * 3. Make API call in background
   * 4. On success: refresh data to get real IDs from backend
   * 5. On failure: revert all optimistic changes
   *
   * This makes the app feel instant while maintaining data consistency.
   *
   * @param product - Partial product data (backend will generate ID)
   * @returns Promise that resolves when operation completes
   *
   * Note: Cache is cleared after successful add to force refresh with real IDs
   */
  const addProduct = useCallback(async (product: Partial<Product>) => {
    console.log('[AppContext] addProduct called:', product);

    try {
      setLoading(true);
      setError(null);

      // ===== OPTIMISTIC UPDATE: Add to UI immediately =====
      const tempId = `temp-${Date.now()}`; // Temporary ID until backend responds
      const optimisticProduct = { ...product, product_id: tempId } as Product;

      console.log(`[AppContext] Optimistically adding product with temp ID: ${tempId}`);
      setProducts(prev => [...prev, optimisticProduct]);

      // ===== OPTIMISTIC UPDATE: Increment summary counts =====
      if (summary && product.product_type) {
        const newSummary: ProductSummary = { ...summary, total: summary.total + 1 };

        // Increment count for this product type (e.g., motors, drives, robot_arms)
        const typePluralKey = `${product.product_type}s`; // motor -> motors, drive -> drives
        if (typePluralKey in newSummary) {
          newSummary[typePluralKey] = (newSummary[typePluralKey] as number || 0) + 1;
          console.log(`[AppContext] Optimistically incremented ${typePluralKey} count to ${newSummary[typePluralKey]}`);
        }

        setSummary(newSummary);
      }

      // ===== API CALL =====
      console.log('[AppContext] Calling API to create product...');
      await apiClient.createProduct(product);
      console.log('[AppContext] Product created successfully');

      // ===== REFRESH DATA =====
      // Clear cache to force refresh with real backend-generated IDs
      console.log('[AppContext] Clearing cache and refreshing data...');
      setProductCache(new Map());
      await loadProducts(currentProductType);
      await loadSummary();
      console.log('[AppContext] Data refresh complete');

    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to add product';
      console.error('[AppContext] Failed to add product:', err);
      setError(errorMsg);

      // ===== REVERT OPTIMISTIC UPDATES =====
      console.warn('[AppContext] Reverting optimistic updates due to error');
      setProductCache(new Map()); // Clear cache
      await loadProducts(currentProductType); // Reload original data
      await loadSummary(); // Reload original summary

    } finally {
      setLoading(false);
    }
  }, [summary, currentProductType, loadProducts, loadSummary]);

  /**
   * Delete a product with optimistic UI update
   *
   * Optimistic Update Pattern:
   * 1. Find product to delete (needed for summary update)
   * 2. Immediately remove from UI (instant feedback)
   * 3. Update summary statistics optimistically
   * 4. Make API call in background
   * 5. On success: clear cache (deletion confirmed)
   * 6. On failure: revert all optimistic changes
   *
   * @param id - Product ID to delete
   * @param type - Product type (needed for API endpoint)
   * @returns Promise that resolves when operation completes
   *
   * Note: Cache is always cleared to prevent showing stale deleted products
   */
  const deleteProduct = useCallback(async (id: string, type: Exclude<ProductType, null>) => {
    console.log(`[AppContext] deleteProduct called for ID: ${id}, type: ${type}`);

    try {
      setLoading(true);
      setError(null);

      // ===== OPTIMISTIC UPDATE: Remove from UI immediately =====
      // First, find the product we're deleting (needed for summary update)
      const deletedProduct = products.find(p => p.product_id === id);

      if (!deletedProduct) {
        console.warn(`[AppContext] Product ${id} not found in current products array`);
      } else {
        console.log(`[AppContext] Found product to delete:`, deletedProduct);
      }

      // Remove from UI immediately
      console.log(`[AppContext] Optimistically removing product ${id} from UI`);
      setProducts(prev => prev.filter(p => p.product_id !== id));

      // ===== OPTIMISTIC UPDATE: Decrement summary counts =====
      if (summary && deletedProduct) {
        const newSummary: ProductSummary = { ...summary, total: summary.total - 1 };

        // Decrement count for this product type (e.g., motors, drives, robot_arms)
        const typePluralKey = `${deletedProduct.product_type}s`; // motor -> motors, drive -> drives
        if (typePluralKey in newSummary) {
          newSummary[typePluralKey] = Math.max(0, (newSummary[typePluralKey] as number || 0) - 1);
          console.log(`[AppContext] Optimistically decremented ${typePluralKey} count to ${newSummary[typePluralKey]}`);
        }

        setSummary(newSummary);
      }

      // ===== API CALL =====
      console.log('[AppContext] Calling API to delete product...');
      await apiClient.deleteProduct(id, type);
      console.log('[AppContext] Product deleted successfully');

      // ===== CLEAR CACHE =====
      // Clear cache to prevent showing deleted product on next load
      console.log('[AppContext] Clearing cache after successful deletion');
      setProductCache(new Map());

    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to delete product';
      console.error('[AppContext] Failed to delete product:', err);
      setError(errorMsg);

      // ===== REVERT OPTIMISTIC UPDATES =====
      console.warn('[AppContext] Reverting optimistic updates due to error');
      setProductCache(new Map()); // Clear cache
      await loadProducts(currentProductType); // Reload original data
      await loadSummary(); // Reload original summary

    } finally {
      setLoading(false);
    }
  }, [products, summary, currentProductType, loadProducts, loadSummary]);

  /**
   * Force refresh all data by clearing cache
   *
   * Use this when you know data has changed externally (e.g., items added
   * directly to DynamoDB) and you want to bypass the cache completely.
   *
   * @returns Promise that resolves when refresh completes
   */
  const forceRefresh = useCallback(async () => {
    console.log('[AppContext] Force refresh: clearing all caches');

    try {
      setLoading(true);
      setError(null);

      // Clear all caches
      setProductCache(new Map());
      setSummary(null);
      setCategories([]);

      // Reload data from scratch
      // Note: loadProducts handles null currentProductType gracefully
      await Promise.all([
        loadProducts(currentProductType),
        loadSummary(),
        loadCategories()
      ]);

      console.log('[AppContext] Force refresh complete');
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to refresh';
      console.error('[AppContext] Force refresh failed:', err);
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [currentProductType, loadProducts, loadSummary, loadCategories]);

  // ========== Context Value Assembly ==========

  /**
   * Assemble all state and methods into the context value
   * This object is provided to all consuming components via useApp()
   */
  const value: AppContextType = {
    // State
    products,       // Currently displayed products
    summary,        // Product statistics (total, motors, drives)
    categories,     // All unique product categories with counts
    loading,        // Global loading indicator
    error,          // Latest error message

    // Data loading methods
    loadProducts,   // Fetch products with intelligent caching
    loadSummary,    // Fetch summary with caching
    loadCategories, // Fetch categories with caching
    forceRefresh,   // Clear cache and force refresh

    // CRUD operations
    addProduct,     // Create new product (optimistic)
    deleteProduct,  // Delete product (optimistic)

    // Direct state setters (use sparingly)
    setProducts,
    setSummary,
    setCategories,
    setError,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

/**
 * Custom hook to access application context
 *
 * Usage:
 * ```tsx
 * function MyComponent() {
 *   const { products, loading, loadProducts } = useApp();
 *   // ... component logic
 * }
 * ```
 *
 * @throws Error if used outside AppProvider
 * @returns AppContextType - All app state and methods
 */
export function useApp() {
  const context = useContext(AppContext);

  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider. ' +
      'Wrap your component tree with <AppProvider> in main.tsx');
  }

  return context;
}
