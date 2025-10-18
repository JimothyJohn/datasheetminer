/**
 * API client for communicating with the backend
 */

import { Product, ProductType, ProductSummary } from '../types/models';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';

interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  count?: number;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Request failed');
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async getSummary(): Promise<ProductSummary> {
    const response = await this.request<ProductSummary>('/api/products/summary');
    if (!response.data) {
      throw new Error('No summary data received');
    }
    return response.data;
  }

  async listProducts(type: ProductType = 'all', limit?: number): Promise<Product[]> {
    const params = new URLSearchParams();
    params.append('type', type);
    if (limit) {
      params.append('limit', limit.toString());
    }

    const response = await this.request<Product[]>(`/api/products?${params}`);
    if (!response.data) {
      throw new Error('No products data received');
    }
    return response.data;
  }

  async getProduct(id: string, type: ProductType): Promise<Product> {
    const response = await this.request<Product>(`/api/products/${id}?type=${type}`);
    if (!response.data) {
      throw new Error('No product data received');
    }
    return response.data;
  }

  async createProduct(product: Partial<Product>): Promise<void> {
    await this.request('/api/products', {
      method: 'POST',
      body: JSON.stringify(product),
    });
  }

  async createProducts(products: Partial<Product>[]): Promise<void> {
    await this.request('/api/products', {
      method: 'POST',
      body: JSON.stringify(products),
    });
  }

  async deleteProduct(id: string, type: ProductType): Promise<void> {
    await this.request(`/api/products/${id}?type=${type}`, {
      method: 'DELETE',
    });
  }
}

export const apiClient = new ApiClient();
export default apiClient;
