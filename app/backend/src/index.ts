/**
 * Main Express application entry point
 */

import path from 'path';
import express, { Application, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import config from './config';
import productsRouter from './routes/products';
import datasheetsRouter from './routes/datasheets';

const app: Application = express();

// Middleware
app.use(cors(config.cors));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Request logging middleware
app.use((req: Request, _res: Response, next: NextFunction) => {
  console.log(`${req.method} ${req.path}`);
  next();
});

// Health check endpoint
app.get('/health', (_req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    environment: config.nodeEnv,
  });
});

// API routes
app.use('/api/products', productsRouter);
app.use('/api/datasheets', datasheetsRouter);

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
🚀 DatasheetMiner API Server
━━━━━━━━━━━━━━━━━━━━━━━━━━
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
