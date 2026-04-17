/**
 * Admin routes — blacklist management and dev/prod data movement.
 *
 * All routes here are gated by the adminOnly middleware (applied once in
 * index.ts when registering the router). Destructive operations default to
 * dry-run; the client must pass apply=true to actually write.
 */

import { Router, Request, Response } from 'express';
import { Blacklist } from '../services/blacklist';
import {
  demote,
  diff,
  expectedPurgeConfirm,
  makeService,
  promote,
  purge,
  PROMOTABLE_PRODUCT_TYPES,
  Stage,
} from '../services/adminOperations';
import { ProductType } from '../types/models';

const router = Router();

const STAGES: Stage[] = ['dev', 'staging', 'prod'];

function isStage(value: unknown): value is Stage {
  return typeof value === 'string' && (STAGES as string[]).includes(value);
}

function isPromotableType(value: unknown): value is ProductType {
  return typeof value === 'string' && (PROMOTABLE_PRODUCT_TYPES as string[]).includes(value);
}

function badRequest(res: Response, error: string): void {
  res.status(400).json({ success: false, error });
}

// ── Blacklist ──────────────────────────────────────────────────────

router.get('/blacklist', (_req: Request, res: Response) => {
  try {
    const bl = new Blacklist();
    res.json({ success: true, data: { banned_manufacturers: bl.names() } });
  } catch (err) {
    console.error('Error reading blacklist:', err);
    res.status(500).json({ success: false, error: 'Failed to read blacklist' });
  }
});

router.post('/blacklist', (req: Request, res: Response) => {
  const manufacturer = typeof req.body?.manufacturer === 'string' ? req.body.manufacturer.trim() : '';
  if (!manufacturer) {
    badRequest(res, 'manufacturer is required');
    return;
  }
  try {
    const bl = new Blacklist();
    const added = bl.add(manufacturer);
    if (added) bl.save();
    res.json({
      success: true,
      data: {
        manufacturer,
        added,
        banned_manufacturers: bl.names(),
      },
    });
  } catch (err) {
    console.error('Error adding to blacklist:', err);
    res.status(500).json({ success: false, error: 'Failed to update blacklist' });
  }
});

router.delete('/blacklist/:name', (req: Request, res: Response) => {
  const manufacturer = req.params.name;
  if (!manufacturer) {
    badRequest(res, 'manufacturer path parameter is required');
    return;
  }
  try {
    const bl = new Blacklist();
    const removed = bl.remove(manufacturer);
    if (removed) bl.save();
    res.json({
      success: true,
      data: {
        manufacturer,
        removed,
        banned_manufacturers: bl.names(),
      },
    });
  } catch (err) {
    console.error('Error removing from blacklist:', err);
    res.status(500).json({ success: false, error: 'Failed to update blacklist' });
  }
});

// ── Diff ───────────────────────────────────────────────────────────

router.post('/diff', async (req: Request, res: Response) => {
  const { source, target, type, manufacturer } = req.body ?? {};
  if (!isStage(source) || !isStage(target)) {
    badRequest(res, 'source and target must each be one of: dev, staging, prod');
    return;
  }
  if (source === target) {
    badRequest(res, 'source and target must differ');
    return;
  }
  if (!isPromotableType(type)) {
    badRequest(res, `type must be one of: ${PROMOTABLE_PRODUCT_TYPES.join(', ')}`);
    return;
  }
  try {
    const result = await diff({
      source: makeService(source),
      target: makeService(target),
      productType: type,
      sourceStage: source,
      targetStage: target,
      manufacturer: typeof manufacturer === 'string' && manufacturer ? manufacturer : undefined,
    });
    res.json({ success: true, data: result });
  } catch (err) {
    console.error('Error running diff:', err);
    res.status(500).json({ success: false, error: 'Diff failed' });
  }
});

// ── Promote / Demote ───────────────────────────────────────────────

async function handlePromoteDemote(
  kind: 'promote' | 'demote',
  req: Request,
  res: Response
): Promise<void> {
  const { source, target, type, manufacturer, apply } = req.body ?? {};
  if (!isStage(source) || !isStage(target)) {
    badRequest(res, 'source and target must each be one of: dev, staging, prod');
    return;
  }
  if (source === target) {
    badRequest(res, 'source and target must differ');
    return;
  }
  if (!isPromotableType(type)) {
    badRequest(res, `type must be one of: ${PROMOTABLE_PRODUCT_TYPES.join(', ')}`);
    return;
  }
  try {
    const srcSvc = makeService(source);
    const tgtSvc = makeService(target);
    const mfg = typeof manufacturer === 'string' && manufacturer ? manufacturer : undefined;
    const doApply = apply === true;

    const result =
      kind === 'promote'
        ? await promote({
            source: srcSvc,
            target: tgtSvc,
            productType: type,
            blacklist: new Blacklist(),
            manufacturer: mfg,
            apply: doApply,
          })
        : await demote({
            source: srcSvc,
            target: tgtSvc,
            productType: type,
            manufacturer: mfg,
            apply: doApply,
          });

    res.json({ success: true, data: result });
  } catch (err) {
    console.error(`Error running ${kind}:`, err);
    res.status(500).json({ success: false, error: `${kind} failed` });
  }
}

router.post('/promote', (req, res) => handlePromoteDemote('promote', req, res));
router.post('/demote', (req, res) => handlePromoteDemote('demote', req, res));

// ── Purge ──────────────────────────────────────────────────────────

router.post('/purge', async (req: Request, res: Response) => {
  const { stage, type, manufacturer, apply, confirm } = req.body ?? {};
  if (!isStage(stage)) {
    badRequest(res, 'stage must be one of: dev, staging, prod');
    return;
  }
  const productType = isPromotableType(type) ? type : undefined;
  const mfg = typeof manufacturer === 'string' && manufacturer ? manufacturer : undefined;
  if (!productType && !mfg) {
    badRequest(res, 'purge requires type and/or manufacturer');
    return;
  }

  const doApply = apply === true;
  const expected = expectedPurgeConfirm(stage, productType, mfg);
  if (doApply && confirm !== expected) {
    res.status(400).json({
      success: false,
      error: 'Confirmation string does not match the purge scope',
      expected,
    });
    return;
  }

  try {
    const result = await purge({
      db: makeService(stage),
      stage,
      productType,
      manufacturer: mfg,
      apply: doApply,
    });
    res.json({ success: true, data: { ...result, expected_confirm: expected } });
  } catch (err) {
    console.error('Error running purge:', err);
    res.status(500).json({
      success: false,
      error: err instanceof Error ? err.message : 'Purge failed',
    });
  }
});

export default router;
