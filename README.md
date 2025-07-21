# Datasheet Miner

Extract technical specifications from product datasheets using AI. Deploy as an AWS Lambda service that analyzes PDFs and returns structured data.

## Quick Start (Local Testing)

1. **Install dependencies**
   ```bash
   # Install uv (Python package manager)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Install project dependencies
   uv sync
   ```

2. **Get Gemini API key**
   - Go to [Google AI Studio](https://aistudio.google.com/)
   - Create an account and generate an API key
   - Add to `.env` file:
   ```bash
   echo "GEMINI_API_KEY=your_api_key_here" > .env
   ```

3. **Run locally**
   ```bash
   ./main.py
   ```

## Deploy to AWS (End-to-End)

### Prerequisites
- AWS account with CLI configured
- AWS SAM CLI installed

### Setup AWS CLI
```bash
# Install AWS CLI
pip install awscli

# Configure with your credentials
aws configure
```

### Install SAM CLI
```bash
# On macOS
brew install aws-sam-cli

# On Linux/Windows - see: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
```

### Deploy
```bash
# Build the application
sam build

# Deploy (first time - creates CloudFormation stack)
sam deploy --guided

# Subsequent deploys
sam deploy
```

### Test Your Deployed API
After deployment, SAM will output your API Gateway URL. Test it:
```bash
# Health check
curl https://your-api-id.execute-api.region.amazonaws.com/Prod/hello

# Analyze a datasheet
curl -X POST https://your-api-id.execute-api.region.amazonaws.com/Prod/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"pdf_url": "https://example.com/datasheet.pdf"}'
```

## What This Does

- Fetches PDF datasheets from URLs
- Uses Google's Gemini AI to extract technical specifications
- Returns structured data about product parameters
- Scales automatically with AWS Lambda
- Costs only when used (serverless pricing)

## Local Development

```bash
# Run tests
pytest

# Format code
ruff format .

# Check code quality
ruff check .

# Start local API server (for testing)
sam local start-api
```
