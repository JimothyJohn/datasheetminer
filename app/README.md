# DatasheetMiner Web Application

A TypeScript web application for viewing and managing product specifications extracted by the DatasheetMiner CLI tools. Provides a REST API and React UI for searching, filtering, and comparing industrial products across manufacturers.

## Features

- **REST API**: Express.js backend with full-text search, filtering, and sorting
- **Web Interface**: React UI with advanced filtering (IS/NOT modes, range sliders, multi-column sort)
- **Gear Ratio Computation**: Auto-compute per-motor gear ratios from torque/speed filter criteria
- **Two App Modes**: Admin (full CRUD, datasheet management) and Public (read-only search)
- **AWS Deployment**: Infrastructure as code with AWS CDK (DynamoDB, API Gateway, Lambda, CloudFront)
- **Tested**: Python unit/integration/staging tests + Jest backend + Vitest frontend

## Product Types

The app supports all product types defined in `datasheetminer/models/`:

| Type | Description |
|------|-------------|
| Motor | AC servo, brushless DC, AC induction, etc. |
| Drive | Servo drives, variable frequency drives |
| Gearhead | Planetary, harmonic, cycloidal reducers |
| Electric Cylinder | Linear actuators with spec data |
| Robot Arm | Industrial robots with per-axis specs |
| Factory | General industrial equipment |

New types are auto-discovered from Pydantic models and appear in the API and UI without code changes.

## Architecture

### Backend (Express + TypeScript)
- REST API with search, product CRUD, datasheet management, upload pipeline
- DynamoDB single-table design (`PK=PRODUCT#TYPE`, `SK=PRODUCT#UUID`)
- Readonly middleware blocks writes in public mode
- TypeScript types mirror Python Pydantic models

### Frontend (React + TypeScript + Vite)
- Product list with multi-attribute filtering and sorting
- Product detail modal with full specs and datasheet links
- Distribution charts for spec value analysis
- Dark/light theme, mobile responsive
- Admin-only pages: Product Management, Datasheets

### Infrastructure (AWS CDK)
- DynamoDB table with PK/SK composite keys
- API Gateway + Lambda (serverless)
- CloudFront + S3 for static frontend
- Stage-isolated tables (products-dev, products-prod)

## Quick Start

### Local Development

```bash
cd app

# Install all dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your AWS credentials and config

# Start development servers
npm run dev

# Backend: http://localhost:3001
# Frontend: http://localhost:3000
```

### Individual Components

```bash
# Backend only
cd backend && npm install && npm run dev

# Frontend only
cd frontend && npm install && npm run dev

# Infrastructure (CDK)
cd infrastructure && npm install && npm run synth
```

## Project Structure

```
app/
├── backend/
│   ├── src/
│   │   ├── index.ts           # Express app entry point
│   │   ├── config/            # Environment configuration
│   │   ├── db/dynamodb.ts     # DynamoDB service (single-table CRUD)
│   │   ├── routes/
│   │   │   ├── products.ts    # Product CRUD + summary/categories/manufacturers
│   │   │   ├── datasheets.ts  # Datasheet management
│   │   │   ├── search.ts      # Full-text search with filters and sort
│   │   │   ├── upload.ts      # Datasheet upload pipeline
│   │   │   ├── subscription.ts # Stripe billing integration
│   │   │   └── docs.ts        # OpenAPI spec serving
│   │   ├── services/
│   │   │   └── search.ts      # Search scoring and filter logic
│   │   ├── middleware/
│   │   │   ├── readonly.ts    # Blocks writes in public mode
│   │   │   └── subscription.ts # Subscription validation
│   │   └── types/models.ts    # TypeScript product interfaces
│   └── tests/                 # Jest tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # Root component with routing
│   │   ├── components/
│   │   │   ├── ProductList.tsx       # Main product display
│   │   │   ├── ProductDetailModal.tsx # Expanded product view
│   │   │   ├── FilterBar.tsx         # Multi-attribute filtering
│   │   │   ├── ProductManagement.tsx  # Admin CRUD UI
│   │   │   ├── DatasheetsPage.tsx    # Admin datasheet management
│   │   │   ├── DistributionChart.tsx  # Spec value charts
│   │   │   └── ...
│   │   ├── api/client.ts      # API client
│   │   ├── context/AppContext.tsx # Global state
│   │   ├── types/models.ts    # TypeScript types
│   │   └── utils/             # Formatting, filtering, hooks
│   └── tests/                 # Vitest tests
├── infrastructure/
│   ├── lib/
│   │   ├── database-stack.ts  # DynamoDB table
│   │   ├── api-stack.ts       # API Gateway + Lambda
│   │   ├── frontend-stack.ts  # CloudFront + S3
│   │   └── config.ts          # Stack configuration
│   └── bin/app.ts             # CDK entry point
├── Dockerfile                 # Multi-stage build (Node 18-alpine)
├── .env.example               # Environment variables template
└── README.md                  # This file
```

## Configuration

### Environment Variables

Create `.env` in the `app/` directory:

```bash
# AWS
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=your-account-id
DYNAMODB_TABLE_NAME=products

# Backend
PORT=3001
NODE_ENV=development
APP_MODE=admin              # admin (full CRUD) or public (read-only)
CORS_ORIGIN=http://localhost:3000

# Frontend
VITE_API_URL=               # Empty for same-origin in production

# Optional: Gemini AI (for upload pipeline)
GEMINI_API_KEY=your-key

# Optional: Stripe billing
STRIPE_LAMBDA_URL=https://your-lambda-url

# Optional: Custom domain
DOMAIN_NAME=api.example.com
CERTIFICATE_ARN=arn:aws:acm:...
HOSTED_ZONE_ID=Z1234567890ABC
```

## API Reference

### Search
```
GET /api/v1/search?q=servo&type=motor&filter=rated_power>=1000&sort=rated_torque:desc&limit=20
```
Full-text search with weighted scoring (part_number > product_name > manufacturer), filter expressions, and multi-field sort.

### Products
```
GET    /api/products                    # List (filter: ?type=motor&limit=50)
GET    /api/products/:id                # Get by ID
GET    /api/products/summary            # Count by type
GET    /api/products/categories          # Product types with counts
GET    /api/products/manufacturers       # Unique manufacturers
GET    /api/products/names              # Unique product names
POST   /api/products                    # Create (admin)
PUT    /api/products/:id                # Update (admin)
DELETE /api/products/:id                # Delete (admin)
```

### Datasheets
```
GET    /api/datasheets                  # List datasheets
GET    /api/datasheets/:id              # Get by ID
POST   /api/datasheets                  # Create (admin)
PUT    /api/datasheets/:id              # Update (admin)
DELETE /api/datasheets/:id              # Delete (admin)
```

### Upload
```
POST   /api/upload                      # Queue datasheet for AI processing (admin)
```

### Health
```
GET    /health                          # Status, mode, timestamp
```

## Testing

```bash
# All tests from app/
npm test

# Backend tests
cd backend && npm test

# Frontend tests
cd frontend && npm test

# With coverage
npm run test:coverage
```

## Deployment

### AWS Deployment

```bash
cd app

# Build everything
npm run build

# Deploy infrastructure
cd infrastructure
cdk bootstrap    # First time only
npm run diff     # Preview changes
npm run deploy   # Deploy all stacks
```

### Docker

```bash
cd app
docker build -t datasheetminer .
docker run -p 3001:3001 \
  -e AWS_REGION=us-east-1 \
  -e DYNAMODB_TABLE_NAME=products \
  -e APP_MODE=public \
  datasheetminer
```

The multi-stage Dockerfile builds frontend (Vite) and backend (TypeScript) separately, producing a minimal Node 18-alpine image that serves both the API and static frontend.

## License

MIT License - See LICENSE file for details.
