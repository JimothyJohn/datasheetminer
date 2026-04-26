/**
 * Compatibility check route — pairwise compat for the rotary motion chain.
 * POST /api/v1/compat/check
 */

import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { DynamoDBService } from '../db/dynamodb';
import { ADJACENT_TYPES, check, isPairSupported, softenReport } from '../services/compat';
import { ProductType } from '../types/models';
import config from '../config';

const router = Router();
const db = new DynamoDBService({ tableName: config.dynamodb.tableName });

const SUPPORTED_TYPES = ['drive', 'motor', 'gearhead'] as const;

const ProductRefSchema = z.object({
  id: z.string().min(1),
  type: z.enum(SUPPORTED_TYPES),
});

const CheckBodySchema = z.object({
  a: ProductRefSchema,
  b: ProductRefSchema,
});

/**
 * POST /api/v1/compat/check
 * Body: { a: { id, type }, b: { id, type } }
 *
 * Returns a CompatibilityReport in fits-partial mode (status is always
 * 'ok' or 'partial'; per-field detail surfaces what didn't line up).
 */
router.post('/check', async (req: Request, res: Response): Promise<void> => {
  const parsed = CheckBodySchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({
      success: false,
      error: 'Invalid request body',
      details: parsed.error.issues.map(i => `${i.path.join('.')}: ${i.message}`),
    });
    return;
  }

  const { a, b } = parsed.data;
  if (!isPairSupported(a.type, b.type)) {
    res.status(400).json({
      success: false,
      error: `Unsupported product pair: ${a.type} + ${b.type}. Supported pairs: drive↔motor, motor↔gearhead.`,
    });
    return;
  }

  try {
    const [productA, productB] = await Promise.all([
      db.read(a.id, a.type as ProductType),
      db.read(b.id, b.type as ProductType),
    ]);

    if (!productA || !productB) {
      res.status(404).json({
        success: false,
        error: !productA && !productB ? 'Both products not found' : !productA ? `Product a (${a.id}) not found` : `Product b (${b.id}) not found`,
      });
      return;
    }

    // Compute strict, soften at the API boundary — UI never gates on `fail`
    // until shared schemas (fieldbus, encoder) are normalised.
    const report = softenReport(check(productA, productB));
    res.json({ success: true, data: report });
  } catch (error) {
    console.error('[compat] Error:', error);
    res.status(500).json({
      success: false,
      error: 'Compatibility check failed',
    });
  }
});

/**
 * GET /api/v1/compat/adjacent?type=<product_type>
 * Returns the list of product types this one can be paired with in the
 * rotary chain. Used by the frontend to scope the picker.
 */
router.get('/adjacent', (req: Request, res: Response): void => {
  const type = String(req.query.type || '');
  const adjacent = ADJACENT_TYPES[type];
  if (!adjacent) {
    res.json({ success: true, data: [] });
    return;
  }
  res.json({ success: true, data: adjacent });
});

export default router;
