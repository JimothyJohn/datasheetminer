/**
 * User-owned Projects — named collections of product refs.
 *
 * All endpoints are `requireAuth`-gated. Identity is read from
 * `req.user.sub`; the URL never carries the owner. A user can only
 * see / mutate their own projects.
 *
 *   GET    /api/projects                          list own projects
 *   POST   /api/projects                          create
 *   GET    /api/projects/:id                      one project
 *   PATCH  /api/projects/:id                      rename
 *   DELETE /api/projects/:id                      delete
 *   POST   /api/projects/:id/products             add product ref
 *   DELETE /api/projects/:id/products/:type/:pid  remove product ref
 */

import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { v4 as uuidv4 } from 'uuid';
import config from '../config';
import { requireAuth } from '../middleware/auth';
import { ProjectsService } from '../db/projects';
import { Project } from '../types/models';

const router = Router();
const db = new ProjectsService({ tableName: config.dynamodb.tableName });

const nameSchema = z.string().trim().min(1, 'Name is required').max(120);
const productRefSchema = z.object({
  product_type: z.string().min(1).max(64),
  product_id: z.string().min(1).max(256),
});
const createSchema = z.object({ name: nameSchema });
const renameSchema = z.object({ name: nameSchema });

function badRequest(res: Response, err: z.ZodError): void {
  res.status(400).json({
    success: false,
    error: 'Invalid request body',
    details: err.issues.map(i => ({ path: i.path.join('.'), message: i.message })),
  });
}

// Strip PK/SK before sending to clients — internal keys, not part of
// the public Project shape.
function publicProject(p: Project): Omit<Project, 'PK' | 'SK'> {
  const { PK: _pk, SK: _sk, ...rest } = p;
  void _pk;
  void _sk;
  return rest;
}

router.use(requireAuth);

router.get('/', async (req: Request, res: Response) => {
  try {
    const projects = await db.list(req.user!.sub);
    res.json({
      success: true,
      data: projects.map(publicProject),
      count: projects.length,
    });
  } catch (err) {
    console.error('[projects] list failed:', err);
    res.status(500).json({ success: false, error: 'Failed to list projects' });
  }
});

router.post('/', async (req: Request, res: Response) => {
  const parsed = createSchema.safeParse(req.body);
  if (!parsed.success) return badRequest(res, parsed.error);

  const now = new Date().toISOString();
  const project: Project = {
    id: uuidv4(),
    name: parsed.data.name,
    owner_sub: req.user!.sub,
    product_refs: [],
    created_at: now,
    updated_at: now,
  };
  try {
    await db.create(req.user!.sub, project);
    res.status(201).json({ success: true, data: publicProject(project) });
  } catch (err) {
    console.error('[projects] create failed:', err);
    res.status(500).json({ success: false, error: 'Failed to create project' });
  }
});

router.get('/:id', async (req: Request, res: Response) => {
  try {
    const project = await db.get(req.user!.sub, req.params.id);
    if (!project) {
      res.status(404).json({ success: false, error: 'Project not found' });
      return;
    }
    res.json({ success: true, data: publicProject(project) });
  } catch (err) {
    console.error('[projects] get failed:', err);
    res.status(500).json({ success: false, error: 'Failed to fetch project' });
  }
});

router.patch('/:id', async (req: Request, res: Response) => {
  const parsed = renameSchema.safeParse(req.body);
  if (!parsed.success) return badRequest(res, parsed.error);

  try {
    const updated = await db.rename(req.user!.sub, req.params.id, parsed.data.name);
    if (!updated) {
      res.status(404).json({ success: false, error: 'Project not found' });
      return;
    }
    res.json({ success: true, data: publicProject(updated) });
  } catch (err) {
    console.error('[projects] rename failed:', err);
    res.status(500).json({ success: false, error: 'Failed to update project' });
  }
});

router.delete('/:id', async (req: Request, res: Response) => {
  try {
    const ok = await db.delete(req.user!.sub, req.params.id);
    if (!ok) {
      res.status(404).json({ success: false, error: 'Project not found' });
      return;
    }
    res.json({ success: true, data: { deleted: true } });
  } catch (err) {
    console.error('[projects] delete failed:', err);
    res.status(500).json({ success: false, error: 'Failed to delete project' });
  }
});

router.post('/:id/products', async (req: Request, res: Response) => {
  const parsed = productRefSchema.safeParse(req.body);
  if (!parsed.success) return badRequest(res, parsed.error);

  try {
    const updated = await db.addProduct(req.user!.sub, req.params.id, parsed.data);
    if (!updated) {
      res.status(404).json({ success: false, error: 'Project not found' });
      return;
    }
    res.json({ success: true, data: publicProject(updated) });
  } catch (err) {
    console.error('[projects] addProduct failed:', err);
    res.status(500).json({ success: false, error: 'Failed to add product' });
  }
});

router.delete('/:id/products/:type/:pid', async (req: Request, res: Response) => {
  try {
    const updated = await db.removeProduct(req.user!.sub, req.params.id, {
      product_type: req.params.type,
      product_id: req.params.pid,
    });
    if (!updated) {
      res.status(404).json({ success: false, error: 'Project not found' });
      return;
    }
    res.json({ success: true, data: publicProject(updated) });
  } catch (err) {
    console.error('[projects] removeProduct failed:', err);
    res.status(500).json({ success: false, error: 'Failed to remove product' });
  }
});

export default router;
