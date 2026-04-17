/**
 * Search route — public API for text search, spec filtering, and sorting.
 * GET /api/v1/search
 */

import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { DynamoDBService } from '../db/dynamodb';
import { ProductType } from '../types/models';
import { searchProducts } from '../services/search';
import config from '../config';

const router = Router();
const db = new DynamoDBService({ tableName: config.dynamodb.tableName });

const SearchQuerySchema = z.object({
  q: z.string().optional(),
  type: z.enum(['motor', 'drive', 'gearhead', 'robot_arm', 'contactor']).optional(),
  manufacturer: z.string().optional(),
  where: z.union([z.string(), z.array(z.string())]).optional(),
  sort: z.union([z.string(), z.array(z.string())]).optional(),
  limit: z.coerce.number().int().min(1).max(100).default(20),
});

/** Normalize string | string[] to string[] */
function toArray(val: string | string[] | undefined): string[] | undefined {
  if (val === undefined) return undefined;
  return Array.isArray(val) ? val : [val];
}

/**
 * GET /api/v1/search
 * Search products with text matching, spec filtering, and sorting.
 */
router.get('/', async (req: Request, res: Response): Promise<void> => {
  try {
    const parsed = SearchQuerySchema.safeParse(req.query);
    if (!parsed.success) {
      console.log('[search] Invalid query params:', parsed.error.issues);
      res.status(400).json({
        success: false,
        error: 'Invalid query parameters',
        details: parsed.error.issues.map(i => `${i.path.join('.')}: ${i.message}`),
      });
      return;
    }

    const { q, type, manufacturer, limit } = parsed.data;
    const where = toArray(parsed.data.where);
    const sort = toArray(parsed.data.sort);

    console.log(`[search] q=${q || ''} type=${type || 'all'} manufacturer=${manufacturer || ''} where=${where?.join(',') || ''} sort=${sort?.join(',') || ''} limit=${limit}`);

    // Fetch products from database
    const productType = (type || 'all') as ProductType;
    const products = await db.list(productType);

    const result = searchProducts({
      products,
      query: q,
      manufacturer,
      where,
      sort,
      limit,
    });

    res.json({
      success: true,
      data: result.products,
      count: result.count,
    });
  } catch (error) {
    console.error('[search] Error:', error);
    res.status(500).json({
      success: false,
      error: 'Search failed',
    });
  }
});

export default router;
