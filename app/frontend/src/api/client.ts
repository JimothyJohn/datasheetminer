/**
 * API Client: HTTP client for backend communication
 *
 * Provides a type-safe, centralized interface for all backend API calls.
 * Uses the Fetch API with automatic JSON serialization and error handling.
 *
 * Key Features:
 * - Environment-aware base URL (VITE_API_URL or localhost:3001)
 * - Automatic Content-Type headers
 * - Centralized error handling
 * - TypeScript generics for type-safe responses
 * - Singleton pattern for consistent client usage
 *
 * Backend Endpoints:
 * - GET  /api/products/summary - Product statistics
 * - GET  /api/products?type=X&limit=Y - List products with filtering
 * - GET  /api/products/:id?type=X - Get single product
 * - POST /api/products - Create product(s)
 * - DELETE /api/products/:id?type=X - Delete product
 *
 * Configuration:
 * - Set VITE_API_URL environment variable to override default backend URL
 * - Vite dev server proxies /api/* to localhost:3001 (see vite.config.ts)
 *
 * @module apiClient
 */

import { Product, ProductSummary, ProductType, DatasheetEntry } from '../types/models';

/**
 * API base URL from environment variable or default to local backend
 * In production: Set VITE_API_URL to your deployed backend URL
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';

/**
 * Default request timeout in milliseconds
 * Prevents requests from hanging indefinitely on slow connections
 */
const DEFAULT_TIMEOUT = 30000; // 30 seconds

/**
 * Maximum number of retry attempts for failed requests
 */
const MAX_RETRIES = 3;

/**
 * Initial delay for exponential backoff (milliseconds)
 */
const INITIAL_RETRY_DELAY = 1000; // 1 second

/**
 * Standard API response wrapper
 * All backend endpoints return this format for consistency
 */
interface ApiResponse<T> {
  success: boolean;    // True if operation succeeded
  data?: T;            // Response data (present on success)
  error?: string;      // Error message (present on failure)
  count?: number;      // Optional count (used by list endpoints)
}

/**
 * API Client class
 *
 * Encapsulates all HTTP communication with the backend.
 * Instantiated as a singleton (exported as `apiClient`).
 */
class ApiClient {
  private baseUrl: string;

  /**
   * Create new API client instance
   * @param baseUrl - Base URL for API requests (default: from env or localhost:3001)
   */
  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    console.log(`[ApiClient] Initialized with base URL: ${this.baseUrl}`);
  }

  /**
   * Generic HTTP request method with retry logic and timeout
   *
   * Handles all HTTP requests with:
   * - Automatic retries with exponential backoff
   * - Request timeout to prevent hanging
   * - Network error detection
   * - Consistent error handling and logging
   *
   * Retry Strategy:
   * - Retry on network errors and 5xx server errors
   * - Don't retry on 4xx client errors (bad request, not found, etc.)
   * - Exponential backoff: 1s, 2s, 4s between retries
   * - Maximum 3 retry attempts
   *
   * Error Handling:
   * 1. Network errors: Retried with exponential backoff
   * 2. Timeout errors: Retried after increasing timeout
   * 3. HTTP 5xx errors: Retried (server temporary issue)
   * 4. HTTP 4xx errors: Not retried (client error)
   * 5. JSON parse errors: Caught and logged
   *
   * @param endpoint - API endpoint path (e.g., '/api/products')
   * @param options - Fetch API options (method, body, headers, etc.)
   * @param retryCount - Current retry attempt (used internally)
   * @returns Promise resolving to ApiResponse<T>
   * @throws Error if request fails after all retries
   *
   * @private Used internally by public methods (getSummary, listProducts, etc.)
   */
  private async request<T>(
    endpoint: string,
    options?: RequestInit,
    retryCount: number = 0
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;
    const method = options?.method || 'GET';

    console.log(`[ApiClient] ${method} ${url}${retryCount > 0 ? ` (retry ${retryCount}/${MAX_RETRIES})` : ''}`);

    try {
      // ===== CREATE ABORT CONTROLLER FOR TIMEOUT =====
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        console.warn(`[ApiClient] Request timeout after ${DEFAULT_TIMEOUT}ms`);
        controller.abort();
      }, DEFAULT_TIMEOUT);

      // ===== MAKE REQUEST WITH TIMEOUT =====
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        signal: controller.signal,
      });

      // Clear timeout on successful response
      clearTimeout(timeoutId);

      // ===== HANDLE HTTP ERRORS =====
      if (!response.ok) {
        // Try to parse error message from response
        let errorMsg = `Request failed with status ${response.status}`;
        try {
          const error = await response.json();
          errorMsg = error.error || errorMsg;
        } catch {
          // Couldn't parse error response, use default message
        }

        console.error(`[ApiClient] HTTP ${response.status} error:`, errorMsg);

        // ===== RETRY ON 5XX SERVER ERRORS =====
        if (response.status >= 500 && retryCount < MAX_RETRIES) {
          const delay = INITIAL_RETRY_DELAY * Math.pow(2, retryCount);
          console.log(`[ApiClient] Server error, retrying in ${delay}ms...`);
          await this.sleep(delay);
          return this.request<T>(endpoint, options, retryCount + 1);
        }

        throw new Error(errorMsg);
      }

      // ===== PARSE JSON RESPONSE =====
      const data = await response.json();
      console.log(`[ApiClient] Response success:`, data.success, `(${data.count || 0} items)`);
      return data;

    } catch (error) {
      // ===== HANDLE NETWORK AND TIMEOUT ERRORS =====
      const isNetworkError = error instanceof TypeError && error.message.includes('fetch');
      const isTimeoutError = error instanceof Error && error.name === 'AbortError';
      const isRetryable = isNetworkError || isTimeoutError;

      if (isRetryable && retryCount < MAX_RETRIES) {
        const delay = INITIAL_RETRY_DELAY * Math.pow(2, retryCount);
        const errorType = isTimeoutError ? 'Timeout' : 'Network error';
        console.warn(`[ApiClient] ${errorType}, retrying in ${delay}ms... (attempt ${retryCount + 1}/${MAX_RETRIES})`);

        await this.sleep(delay);
        return this.request<T>(endpoint, options, retryCount + 1);
      }

      // ===== ALL RETRIES EXHAUSTED OR NON-RETRYABLE ERROR =====
      const errorMsg = error instanceof Error ? error.message : 'Request failed';
      console.error(`[ApiClient] Request failed after ${retryCount} retries:`, errorMsg);

      // Throw user-friendly error message
      if (isTimeoutError) {
        throw new Error('Request timed out. Please check your internet connection and try again.');
      }
      if (isNetworkError) {
        throw new Error('Network error. Please check your internet connection and try again.');
      }

      throw error;
    }
  }

  /**
   * Sleep utility for exponential backoff delays
   * @param ms - Milliseconds to sleep
   * @private
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // ========== Public API Methods ==========

  /**
   * Get all unique product categories with counts
   *
   * Fetches all product types that exist in the database, along with their counts.
   * Returns dynamic list that updates as new product types are added.
   * Used by Dashboard and ProductList components for category selection.
   *
   * Backend Endpoint: GET /api/products/categories
   *
   * @returns Promise<Array<{ type: string; count: number; display_name: string }>>
   * @throws Error if request fails or no data received
   *
   * Performance: ~100-300ms (scans all products to determine types)
   */
  async getCategories(): Promise<Array<{ type: string; count: number; display_name: string }>> {
    const response = await this.request<Array<{ type: string; count: number; display_name: string }>>(
      '/api/products/categories'
    );

    if (!response.data) {
      throw new Error('No categories data received');
    }

    console.log(`[ApiClient] Received ${response.data.length} product categories`);
    return response.data;
  }

  /**
   * Get product summary statistics
   *
   * Fetches aggregated counts: total products, total motors, total drives.
   * Used by Dashboard component to display summary cards.
   *
   * Backend Endpoint: GET /api/products/summary
   *
   * @returns Promise<ProductSummary> - { total, motors, drives }
   * @throws Error if request fails or no data received
   *
   * Performance: ~50-150ms (DynamoDB scan aggregation)
   */
  async getSummary(): Promise<ProductSummary> {
    const response = await this.request<ProductSummary>('/api/products/summary');

    if (!response.data) {
      throw new Error('No summary data received');
    }

    return response.data;
  }

  /**
   * List products with optional filtering
   *
   * Fetches products from backend with type filtering and optional limit.
   * Used by ProductList component with AppContext caching.
   *
   * Backend Endpoint: GET /api/products?type=X&limit=Y
   *
   * Query Parameters:
   * - type: 'motor' | 'drive' | 'all' (default: 'all')
   * - limit: Maximum number of products to return (optional)
   *
   * @param type - Product type filter ('motor', 'drive', or 'all')
   * @param limit - Optional limit on number of results
   * @returns Promise<Product[]> - Array of products matching filter
   * @throws Error if request fails or no data received
   *
   * Performance: ~100-500ms depending on product count (DynamoDB query)
   */
  async listProducts(type: Exclude<ProductType, null> = 'all', limit?: number): Promise<Product[]> {
    const params = new URLSearchParams();
    if (type !== 'datasheet') {
      params.append('type', type);
    }
    if (limit) {
      params.append('limit', limit.toString());
    }

    const endpoint = type === 'datasheet' ? '/api/datasheets' : `/api/products?${params}`;
    const response = await this.request<Product[]>(endpoint);

    if (!response.data) {
      throw new Error('No products data received');
    }

    console.log(`[ApiClient] Received ${response.data.length} products of type '${type}'`);
    return response.data;
  }

  /**
   * Get a single product by ID
   *
   * Fetches complete product details for a specific product.
   * Type parameter required for DynamoDB composite key (PK: type, SK: product_id).
   *
   * Backend Endpoint: GET /api/products/:id?type=X
   *
   * @param id - Product ID (part_number or product_id)
   * @param type - Product type ('motor' or 'drive')
   * @returns Promise<Product> - Complete product object
   * @throws Error if product not found or request fails
   *
   * Performance: ~50-100ms (DynamoDB GetItem)
   */
  async getProduct(id: string, type: ProductType): Promise<Product> {
    const response = await this.request<Product>(`/api/products/${id}?type=${type}`);

    if (!response.data) {
      throw new Error('No product data received');
    }

    return response.data;
  }

  /**
   * Create a single product
   *
   * Creates a new product in the database.
   * Backend generates product_id if not provided.
   *
   * Backend Endpoint: POST /api/products
   * Request Body: Partial<Product> (product_type required)
   *
   * @param product - Partial product data (at minimum: product_type)
   * @returns Promise<void> - Resolves on success
   * @throws Error if creation fails or validation error
   *
   * Performance: ~100-200ms (DynamoDB PutItem)
   *
   * Note: AppContext will refresh data after successful creation to get generated ID
   */
  async createProduct(product: Partial<Product>): Promise<void> {
    console.log('[ApiClient] Creating single product:', product.part_number || 'unnamed');

    await this.request('/api/products', {
      method: 'POST',
      body: JSON.stringify(product),
    });
  }

  /**
   * Create multiple products (batch)
   *
   * Creates multiple products in a single request.
   * More efficient than multiple createProduct calls.
   *
   * Backend Endpoint: POST /api/products
   * Request Body: Partial<Product>[] (array of products)
   *
   * @param products - Array of partial product data
   * @returns Promise<void> - Resolves when all products created
   * @throws Error if any creation fails
   *
   * Performance: ~200-500ms depending on count (DynamoDB BatchWriteItem)
   *
   * Note: Backend automatically detects array vs single object
   */
  async createProducts(products: Partial<Product>[]): Promise<void> {
    console.log(`[ApiClient] Creating ${products.length} products in batch`);

    await this.request('/api/products', {
      method: 'POST',
      body: JSON.stringify(products),
    });
  }

  /**
   * Update a datasheet
   */
  async updateDatasheet(id: string, updates: Partial<DatasheetEntry>): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/datasheets/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to update datasheet');
    }
  }

  /**
   * Delete a product
   *
   * Permanently deletes a product from the database.
   * Type parameter required for DynamoDB composite key.
   *
   * Backend Endpoint: DELETE /api/products/:id?type=X
   *
   * @param id - Product ID to delete
   * @param type - Product type ('motor' or 'drive')
   * @returns Promise<void> - Resolves on successful deletion
   * @throws Error if product not found or deletion fails
   *
   * Performance: ~50-150ms (DynamoDB DeleteItem)
   *
   * Warning: This operation is irreversible!
   */
  async deleteProduct(id: string, type: Exclude<ProductType, null>, componentType?: string): Promise<void> {
    console.log(`[ApiClient] Deleting product: ${id} (type: ${type}, componentType: ${componentType})`);

    // If deleting a datasheet, we need to pass the actual component type (e.g. 'motor')
    // so the backend can construct the correct PK (DATASHEET#MOTOR)
    const typeParam = type === 'datasheet' && componentType ? componentType : type;

    const endpoint = type === 'datasheet' 
      ? `/api/datasheets/${id}?type=${typeParam}` 
      : `/api/products/${id}?type=${typeParam}`;

    await this.request(endpoint, {
      method: 'DELETE',
    });
  }
}

// ========== Singleton Export ==========

/**
 * Singleton API client instance
 *
 * Import and use this instance throughout the application:
 * ```typescript
 * import { apiClient } from './api/client';
 * const products = await apiClient.listProducts('motor');
 * ```
 *
 * Ensures consistent configuration and avoids creating multiple instances.
 */
export const apiClient = new ApiClient();

/**
 * Default export (alternative import method)
 * ```typescript
 * import apiClient from './api/client';
 * ```
 */
export default apiClient;
