/**
 * API routes for products
 * Mirrors functionality from query.py and pusher.py
 */

import { Router, Request, Response } from 'express';
import { DynamoDBService } from '../db/dynamodb';
import { Product, ProductType } from '../types/models';
import { v4 as uuidv4 } from 'uuid';
import config from '../config';

const router = Router();
const db = new DynamoDBService({ tableName: config.dynamodb.tableName });

/**
 * GET /api/products/categories
 * Get all unique product categories with counts
 */
router.get('/categories', async (_req: Request, res: Response) => {
  try {
    const categories = await db.getCategories();
    res.json({
      success: true,
      data: categories,
    });
  } catch (error) {
    console.error('Error getting categories:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to get categories',
    });
  }
});

/**
 * GET /api/products/summary
 * Get summary statistics about products in the database
 */
router.get('/summary', async (_req: Request, res: Response) => {
  try {
    const counts = await db.count();
    res.json({
      success: true,
      data: counts,
    });
  } catch (error) {
    console.error('Error getting summary:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to get summary',
    });
  }
});

/**
 * GET /api/products
 * List products with optional filtering
 * Query params: type (any product type or 'all'), limit (number)
 */
router.get('/', async (req: Request, res: Response): Promise<void> => {
  try {
    const type = (req.query.type as ProductType) || 'all';
    const limit = req.query.limit ? parseInt(req.query.limit as string, 10) : undefined;

    // Accept any product type - no validation needed
    // The database will return empty array if type doesn't exist

    const products = await db.list(type, limit);

    res.json({
      success: true,
      data: products,
      count: products.length,
    });
  } catch (error) {
    console.error('Error listing products:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to list products',
    });
  }
});

/**
 * GET /api/products/:id
 * Get a specific product by ID
 * Query params: type (any valid product type) - required
 */
router.get('/:id', async (req: Request, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const type = req.query.type as ProductType;

    if (!type) {
      res.status(400).json({
        success: false,
        error: 'type query parameter is required',
      });
      return;
    }

    const product = await db.read(id, type);

    if (!product) {
      res.status(404).json({
        success: false,
        error: 'Product not found',
      });
      return;
    }

    res.json({
      success: true,
      data: product,
    });
  } catch (error) {
    console.error('Error getting product:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to get product',
    });
  }
});

/**
 * POST /api/products
 * Create a new product or batch create multiple products
 * Body: Product | Product[]
 */
router.post('/', async (req: Request, res: Response): Promise<void> => {
  try {
    const body = req.body;

    // Handle both single product and array of products
    const products: Product[] = Array.isArray(body) ? body : [body];

    // Validate products have required fields
    for (const product of products) {
      if (!product.product_type) {
        res.status(400).json({
          success: false,
          error: 'Each product must have a product_type field',
        });
        return;
      }

      // Generate product_id if not provided
      if (!product.product_id) {
        product.product_id = uuidv4();
      }
    }

    // Use batch create if multiple products
    let successCount: number;
    if (products.length > 1) {
      successCount = await db.batchCreate(products);
    } else {
      const success = await db.create(products[0]);
      successCount = success ? 1 : 0;
    }

    const failureCount = products.length - successCount;

    res.status(201).json({
      success: successCount > 0,
      data: {
        items_received: products.length,
        items_created: successCount,
        items_failed: failureCount,
      },
    });
  } catch (error) {
    console.error('Error creating product(s):', error);
    res.status(500).json({
      success: false,
      error: 'Failed to create product(s)',
    });
  }
});

/**
 * DELETE /api/products/:id
 * Delete a product by ID
 * Query params: type (any valid product type) - required
 */
router.delete('/:id', async (req: Request, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const type = req.query.type as ProductType;

    if (!type) {
      res.status(400).json({
        success: false,
        error: 'type query parameter is required',
      });
      return;
    }

    const success = await db.delete(id, type);

    if (!success) {
      res.status(404).json({
        success: false,
        error: 'Product not found or failed to delete',
      });
      return;
    }

    res.json({
      success: true,
      message: 'Product deleted successfully',
    });
  } catch (error) {
    console.error('Error deleting product:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to delete product',
    });
  }
});

export default router;
