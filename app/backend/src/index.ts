/**
 * Main Express application entry point
 */

import path from 'path';
import express, { Application, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import config from './config';
import { readonlyGuard } from './middleware/readonly';
import { adminOnly } from './middleware/adminOnly';
import productsRouter from './routes/products';
import datasheetsRouter from './routes/datasheets';
import uploadRouter from './routes/upload';
import subscriptionRouter from './routes/subscription';
import searchRouter from './routes/search';
import docsRouter from './routes/docs';
import adminRouter from './routes/admin';

const app: Application = express();

// Security: don't leak server technology
app.disable('x-powered-by');

// Middleware
app.use(cors(config.cors));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Request logging middleware
app.use((req: Request, _res: Response, next: NextFunction) => {
  console.log(`[${config.appMode}] ${req.method} ${req.path}`);
  next();
});

// Readonly guard — blocks writes in public mode
if (config.appMode === 'public') {
  console.log('[server] Public mode: write operations disabled');
  app.use('/api', readonlyGuard);
}

// Health check endpoint
app.get('/health', (_req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    environment: config.nodeEnv,
    mode: config.appMode,
  });
});

// Upload route — available in both public and admin mode (queues only, no data mutation)
app.use('/api/upload', uploadRouter);

// API routes
app.use('/api/products', productsRouter);
app.use('/api/datasheets', datasheetsRouter);
app.use('/api/subscription', subscriptionRouter);
app.use('/api/v1/search', searchRouter);
app.use('/api/admin', adminOnly, adminRouter);
app.use('/api', docsRouter);

// Serve frontend static files in production (Docker container)
if (process.env.NODE_ENV === 'production') {
  const publicDir = path.join(__dirname, '..', '..', 'public');
  app.use(express.static(publicDir));
  app.get('*', (_req: Request, res: Response, next: NextFunction) => {
    if (_req.path.startsWith('/api/') || _req.path === '/health') return next();
    res.sendFile(path.join(publicDir, 'index.html'));
  });
}

// Root endpoint
app.get('/', (_req: Request, res: Response) => {
  res.json({
    name: 'DatasheetMiner API',
    version: '1.0.0',
    endpoints: {
      health: '/health',
      products: '/api/products',
      datasheets: '/api/datasheets',
      summary: '/api/products/summary',
      subscription: '/api/subscription',
      search: '/api/v1/search',
      openapi: '/api/openapi.json',
      docs: '/api/docs',
    },
  });
});

// 404 handler
app.use((_req: Request, res: Response) => {
  res.status(404).json({
    success: false,
    error: 'Endpoint not found',
  });
});

// Error handler
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error('Error:', err);
  res.status(500).json({
    success: false,
    error: 'Internal server error',
    message: config.nodeEnv === 'development' ? err.message : undefined,
  });
});

// Start server (only if not imported)
if (require.main === module) {
  app.listen(config.port, () => {
    console.log(`
DatasheetMiner API Server
━━━━━━━━━━━━━━━━━━━━━━━━━━
Mode: ${config.appMode}
Environment: ${config.nodeEnv}
Port: ${config.port}
DynamoDB Table: ${config.dynamodb.tableName}
AWS Region: ${config.aws.region}
━━━━━━━━━━━━━━━━━━━━━━━━━━
Ready to accept connections!
    `);
  });
}

export default app;
