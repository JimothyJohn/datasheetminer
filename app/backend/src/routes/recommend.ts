/**
 * API route for product recommendations.
 * Accepts user requirements via chat and returns AI-powered product suggestions.
 */

import { Router, Request, Response } from 'express';
import { DynamoDBService } from '../db/dynamodb';
import { RecommendationService } from '../services/recommendation';
import config from '../config';

const router = Router();
const db = new DynamoDBService({ tableName: config.dynamodb.tableName });
const recommendationService = new RecommendationService();

/**
 * POST /api/recommend
 * Body: { message: string, history?: Array<{ role: 'user'|'model', content: string }> }
 * Returns: { success: true, data: { response: string, products: Product[] } }
 */
router.post('/', async (req: Request, res: Response) => {
  try {
    const { message, history } = req.body;

    if (!message || typeof message !== 'string' || message.trim().length === 0) {
      res.status(400).json({
        success: false,
        error: 'Message is required',
      });
      return;
    }

    if (!config.gemini.apiKey) {
      res.status(503).json({
        success: false,
        error: 'Recommendation service is not configured',
      });
      return;
    }

    // Get products from cache or DynamoDB
    let products = recommendationService.getCachedProducts();
    if (!products) {
      console.log('[recommend] Cache miss — fetching products from DynamoDB');
      products = await db.listAll();
      recommendationService.setCachedProducts(products);
      console.log(`[recommend] Cached ${products.length} products`);
    } else {
      console.log(`[recommend] Cache hit — ${products.length} products`);
    }

    // Call Gemini for recommendation
    const result = await recommendationService.recommend(
      message.trim(),
      products,
      history || [],
    );

    // Resolve recommended product IDs to full product objects
    const productMap = new Map(
      products.filter((p): p is Exclude<typeof p, { datasheet_id?: string }> => 'product_id' in p)
        .map((p: any) => [p.product_id, p])
    );
    const recommendedProducts = result.recommended_product_ids
      .map((id) => productMap.get(id))
      .filter(Boolean);

    res.json({
      success: true,
      data: {
        response: result.response,
        products: recommendedProducts,
      },
    });
  } catch (error: any) {
    console.error('[recommend] Error:', error.message || error);
    res.status(500).json({
      success: false,
      error: 'Failed to generate recommendation. Please try again.',
    });
  }
});

export default router;
