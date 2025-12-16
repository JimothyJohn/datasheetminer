# DatasheetMiner Web Application

A modern TypeScript-based web application for viewing and managing product datasheets. This application provides a REST API and web interface for the data extracted by the DatasheetMiner CLI tool.

## Features

- **REST API**: Express.js backend with TypeScript for type-safe operations
- **Web Interface**: React-based UI for viewing and managing products
- **AWS Deployment**: Infrastructure as code with AWS CDK
- **DynamoDB Integration**: Efficient data storage with single-table design
- **HTTPS Support**: Optional custom domain with SSL certificate
- **CI/CD Ready**: GitHub Actions workflow for automated testing and deployment
- **Fully Tested**: Comprehensive test coverage for both backend and frontend
- **Minimalistic Design**: Clean, intuitive interface that's easy to use and extend

## Architecture

### Backend (Express + TypeScript)
- REST API for data management
- DynamoDB service for CRUD operations
- TypeScript types mirror application data models
- Environment-based configuration
- Request validation and error handling

### Frontend (React + TypeScript)
- Dashboard showing summary statistics
- Product list with filtering (motors, drives, all)
- Responsive design
- Type-safe API client
- Modern React with hooks

### Infrastructure (AWS CDK)
- DynamoDB table with PK/SK design
- API Gateway + Lambda (serverless)
- Optional custom domain with HTTPS
- Infrastructure as code
- Environment-based configuration

## Prerequisites

- **Node.js**: 18.0.0 or higher
- **npm**: 9.0.0 or higher
- **AWS Account**: For deployment (optional for local development)
- **AWS CLI**: Configured with credentials (for deployment)

## Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/jimothyjohn/datasheetminer.git
cd datasheetminer/app

# Install all dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Start development servers
npm run dev

# Backend will run on http://localhost:3001
# Frontend will run on http://localhost:3000
```

### Individual Components

```bash
# Backend only
cd backend
npm install
npm run dev

# Frontend only
cd frontend
npm install
npm run dev

# Infrastructure (CDK)
cd infrastructure
npm install
npm run synth  # Generate CloudFormation templates
```

## Project Structure

```
app/
├── backend/                 # Express.js API
│   ├── src/
│   │   ├── index.ts         # Express app entry point
│   │   ├── config/          # Configuration management
│   │   ├── db/              # DynamoDB service
│   │   ├── routes/          # API routes
│   │   └── types/           # TypeScript types
│   ├── tests/               # Backend tests
│   ├── package.json         # Backend dependencies
│   └── tsconfig.json        # TypeScript config
├── frontend/                # React application
│   ├── src/
│   │   ├── App.tsx          # Main React app
│   │   ├── main.tsx         # Entry point
│   │   ├── components/      # React components
│   │   ├── api/             # API client
│   │   └── types/           # TypeScript types
│   ├── public/              # Static assets
│   ├── package.json         # Frontend dependencies
│   └── vite.config.ts       # Vite configuration
├── infrastructure/          # AWS CDK
│   ├── lib/
│   │   ├── database-stack.ts  # DynamoDB table
│   │   ├── api-stack.ts       # API Gateway + Lambda
│   │   └── config.ts          # Configuration
│   ├── bin/
│   │   └── app.ts           # CDK app entry point
│   └── cdk.json             # CDK configuration
├── .github/                 # CI/CD workflows
│   └── workflows/
│       └── ci.yml           # GitHub Actions
├── package.json             # Root package.json (workspaces)
├── .env.example             # Example environment variables
└── README.md                # This file
```

## Configuration

### Environment Variables

Create a `.env` file in the `app/` directory:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=your-account-id
DYNAMODB_TABLE_NAME=products

# Backend Configuration
PORT=3001
NODE_ENV=development

# Frontend Configuration
REACT_APP_API_URL=http://localhost:3001

# Optional: Domain and HTTPS Configuration
DOMAIN_NAME=api.example.com
CERTIFICATE_ARN=arn:aws:acm:region:account:certificate/id
HOSTED_ZONE_ID=Z1234567890ABC
```

### Backend Configuration

The backend uses environment variables for configuration:

- `PORT`: Server port (default: 3001)
- `NODE_ENV`: Environment (development, production)
- `AWS_REGION`: AWS region for DynamoDB
- `DYNAMODB_TABLE_NAME`: DynamoDB table name
- `CORS_ORIGIN`: CORS allowed origins

### Frontend Configuration

The frontend uses Vite environment variables:

- `VITE_API_URL`: Backend API URL

## API Reference

### Endpoints

#### Health Check
```
GET /health
```
Returns health status of the API.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-14T12:00:00.000Z",
  "environment": "development"
}
```

#### Get Summary
```
GET /api/products/summary
```
Get product counts and statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "total": 100,
    "motors": 60,
    "drives": 40
  }
}
```

#### List Products
```
GET /api/products?type={motor|drive|all}&limit={number}
```
List products with optional filtering.

**Query Parameters:**
- `type` (optional): Filter by product type (motor, drive, all)
- `limit` (optional): Maximum number of products to return

**Response:**
```json
{
  "success": true,
  "data": [...],
  "count": 10
}
```

#### Get Product by ID
```
GET /api/products/:id?type={motor|drive}
```
Get a specific product by ID.

**Query Parameters:**
- `type` (required): Product type (motor or drive)

**Response:**
```json
{
  "success": true,
  "data": {
    "product_id": "123",
    "product_type": "motor",
    ...
  }
}
```

#### Create Product(s)
```
POST /api/products
```
Create one or more products.

**Request Body:**
```json
{
  "product_type": "motor",
  "manufacturer": "ACME Motors",
  "part_number": "AC-2300-5HP",
  ...
}
```

Or array for batch create:
```json
[
  { "product_type": "motor", ... },
  { "product_type": "drive", ... }
]
```

**Response:**
```json
{
  "success": true,
  "data": {
    "items_received": 2,
    "items_created": 2,
    "items_failed": 0
  }
}
```

#### Delete Product
```
DELETE /api/products/:id?type={motor|drive}
```
Delete a product by ID.

**Query Parameters:**
- `type` (required): Product type (motor or drive)

**Response:**
```json
{
  "success": true,
  "message": "Product deleted successfully"
}
```

## Testing

### Run All Tests
```bash
# From app/ directory
npm test

# With coverage
npm run test:coverage
```

### Backend Tests
```bash
cd backend
npm test
npm run test:watch     # Watch mode
npm run test:coverage  # Coverage report
```

### Frontend Tests
```bash
cd frontend
npm test
npm run test:ui        # UI mode
npm run test:coverage  # Coverage report
```

## Building

### Development Build
```bash
npm run build
```

This builds both backend and frontend.

### Production Build
```bash
NODE_ENV=production npm run build
```

### Build Individual Components
```bash
# Backend
cd backend && npm run build

# Frontend
cd frontend && npm run build
```

## Deployment

### Prerequisites for AWS Deployment

1. **AWS CLI** configured with credentials:
   ```bash
   aws configure
   ```

2. **AWS CDK** installed:
   ```bash
   npm install -g aws-cdk
   ```

3. **Environment variables** set (see Configuration section)

### Deploy to AWS

```bash
cd app

# Build everything
npm run build

# Deploy infrastructure
cd infrastructure

# Bootstrap CDK (first time only)
cdk bootstrap

# Review changes
npm run diff

# Deploy
npm run deploy

# Or deploy all stacks
npm run deploy:all
```

### Manual Deployment Steps

1. **Build backend:**
   ```bash
   cd backend
   npm ci
   npm run build
   ```

2. **Build frontend:**
   ```bash
   cd frontend
   npm ci
   npm run build
   ```

3. **Deploy infrastructure:**
   ```bash
   cd infrastructure
   npm ci

   # Set environment variables
   export AWS_ACCOUNT_ID=your-account-id
   export AWS_REGION=us-east-1
   export DYNAMODB_TABLE_NAME=products

   # Deploy
   npm run deploy:all
   ```

### HTTPS and Custom Domain

To enable HTTPS with a custom domain:

1. **Create ACM certificate** in AWS Certificate Manager
2. **Create Route 53 hosted zone** (if not already created)
3. **Set environment variables:**
   ```bash
   export DOMAIN_NAME=api.example.com
   export CERTIFICATE_ARN=arn:aws:acm:...
   export HOSTED_ZONE_ID=Z1234567890ABC
   ```
4. **Deploy:**
   ```bash
   cd infrastructure
   npm run deploy:all
   ```

The CDK will automatically configure:
- API Gateway custom domain
- Route 53 DNS records
- SSL/TLS termination

## CI/CD

### GitHub Actions

The repository includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that:

1. Runs tests for backend and frontend on every push
2. Builds both components
3. Deploys to AWS on push to main/master branch

### Required GitHub Secrets

Add these secrets to your GitHub repository:

```
AWS_ACCESS_KEY_ID          # AWS access key
AWS_SECRET_ACCESS_KEY      # AWS secret key
AWS_REGION                 # AWS region (e.g., us-east-1)
AWS_ACCOUNT_ID             # AWS account ID
DYNAMODB_TABLE_NAME        # DynamoDB table name (optional, defaults to 'products')

# Optional: For HTTPS
DOMAIN_NAME                # Custom domain name
CERTIFICATE_ARN            # ACM certificate ARN
HOSTED_ZONE_ID             # Route 53 hosted zone ID
```

### Manual Workflow Trigger

You can manually trigger the workflow from the GitHub Actions tab.

## Development

### Code Style

#### Backend
- **TypeScript**: Strict mode enabled
- **Linting**: ESLint with TypeScript rules
- **Formatting**: Automatic via ESLint
- **Testing**: Jest with supertest

#### Frontend
- **TypeScript**: Strict mode enabled
- **Linting**: ESLint with React rules
- **Formatting**: Automatic via ESLint
- **Testing**: Vitest with React Testing Library

### Linting

```bash
# Lint everything
npm run lint

# Lint with auto-fix
npm run lint:fix

# Lint backend only
cd backend && npm run lint

# Lint frontend only
cd frontend && npm run lint
```

### Adding New Features

#### Adding a New API Endpoint

1. Define route in `backend/src/routes/`
2. Add types to `backend/src/types/models.ts`
3. Update tests in `backend/tests/`
4. Update API client in `frontend/src/api/client.ts`

#### Adding a New React Component

1. Create component in `frontend/src/components/`
2. Add types to `frontend/src/types/`
3. Import and use in `App.tsx` or other components
4. Add tests in `frontend/src/components/`

#### Modifying Infrastructure

1. Update stacks in `infrastructure/lib/`
2. Update configuration in `infrastructure/lib/config.ts`
3. Run `npm run synth` to verify
4. Run `npm run diff` to preview changes
5. Deploy with `npm run deploy`

## Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Find and kill process using port 3001
lsof -ti:3001 | xargs kill -9

# Or use different port
PORT=3002 npm run dev:backend
```

#### DynamoDB Connection Issues
- Verify AWS credentials: `aws sts get-caller-identity`
- Check AWS_REGION environment variable
- Verify table exists: `aws dynamodb describe-table --table-name products`

#### Build Failures
```bash
# Clean and rebuild
rm -rf node_modules package-lock.json
rm -rf backend/node_modules backend/package-lock.json
rm -rf frontend/node_modules frontend/package-lock.json
npm install
npm run build
```

#### CDK Deployment Failures
```bash
# Check CDK version
cdk --version

# Re-bootstrap if needed
cdk bootstrap

# Check for differences
npm run diff

# Deploy with verbose logging
CDK_DEBUG=true npm run deploy
```

### Debug Mode

Enable debug logging:

```bash
# Backend
DEBUG=* npm run dev:backend

# CDK
CDK_DEBUG=true npm run deploy
```

## Performance

### Optimization Tips

1. **DynamoDB**: Use batch operations for multiple items
2. **API Gateway**: Enable caching for frequently accessed endpoints
3. **Lambda**: Adjust memory settings in `api-stack.ts`
4. **Frontend**: Lazy load components with React.lazy()

### Monitoring

After deployment, monitor your application:

- **CloudWatch Logs**: Check Lambda function logs
- **CloudWatch Metrics**: Monitor API Gateway and DynamoDB metrics
- **X-Ray**: Enable for distributed tracing
- **DynamoDB**: Monitor read/write capacity

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `npm test`
5. Run linter: `npm run lint`
6. Commit changes: `git commit -am 'Add my feature'`
7. Push to branch: `git push origin feature/my-feature`
8. Create a Pull Request

## License

MIT License - See LICENSE file for details.

## Support

- **Documentation**: See CLAUDE.md in root directory
- **Issues**: Report bugs via [GitHub Issues](https://github.com/jimothyjohn/datasheetminer/issues)
- **Main Project**: [DatasheetMiner](https://github.com/jimothyjohn/datasheetminer)

## Acknowledgments

- Built with [Express.js](https://expressjs.com/)
- UI powered by [React](https://react.dev/)
- Infrastructure managed by [AWS CDK](https://aws.amazon.com/cdk/)
- TypeScript types mirror [Pydantic](https://docs.pydantic.dev/) models from the Python CLI
