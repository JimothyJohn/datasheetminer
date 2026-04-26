/**
 * API documentation routes — serves OpenAPI spec and interactive docs.
 */

import { Router, Request, Response } from 'express';
import spec from '../openapi.json';

const router = Router();

/**
 * GET /api/openapi.json
 * Raw OpenAPI 3.1 spec for agents and tooling.
 */
router.get('/openapi.json', (_req: Request, res: Response) => {
  res.json(spec);
});

/**
 * GET /api/docs
 * Interactive API documentation using Scalar (loaded from CDN).
 */
router.get('/docs', (_req: Request, res: Response) => {
  res.type('html').send(`<!DOCTYPE html>
<html>
<head>
  <title>Specodex API Docs</title>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body>
  <script id="api-reference" data-url="/api/openapi.json"></script>
  <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>`);
});

export default router;
