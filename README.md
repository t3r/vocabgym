# VocabTrainer

A web-based French vocabulary training application for 9th grade German Gymnasium students. Students scan workbook pages, automatically extract vocabulary using AI/OCR, review and edit the results, and practice with typing-based exercises.

## Architecture Overview

- **Frontend**: Vue 3 (Composition API) + Tailwind CSS, built with Vite, deployed to S3 + CloudFront
- **Backend**: AWS Lambda (Python 3.11+) behind API Gateway
- **Database**: Amazon DynamoDB
- **Storage**: Amazon S3 (images and static hosting)
- **Authentication**: AWS Cognito (OAuth2 with hosted UI)
- **OCR**: AWS Textract (primary), OpenAI Vision API (fallback)

## Prerequisites

- Node.js 18+
- Python 3.11+
- AWS CLI configured with appropriate credentials
- AWS SAM CLI (`brew install aws-sam-cli`)
- Docker (required for `sam local`) — install via `brew install --cask docker`
- Git

## Quick Start

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server runs at http://localhost:5173.

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run locally with SAM
sam local start-api
```

The local API runs at http://localhost:3000.

## Project Structure

```
vocabgym/
├── frontend/               # Vue 3 application
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── views/          # Page-level components
│   │   ├── stores/         # Pinia state management
│   │   ├── services/       # API and auth services
│   │   ├── composables/    # Composition API utilities
│   │   ├── router/         # Vue Router configuration
│   │   └── utils/          # Helper functions
│   └── package.json
├── backend/                # Lambda functions + infrastructure
│   ├── template.yaml       # SAM/CloudFormation template
│   ├── samconfig.toml      # SAM deployment config
│   ├── functions/
│   │   ├── upload_handler/
│   │   ├── extraction_handler/
│   │   ├── vocab_crud_handler/
│   │   ├── practice_handler/
│   │   └── progress_handler/
│   ├── layers/             # Shared Lambda layer
│   └── tests/
└── README.md
```

## Deployment

### Backend

```bash
cd backend
sam build
sam deploy --guided
```

### Frontend

```bash
cd frontend
npm run build
aws s3 sync dist/ s3://vocabtrainer-frontend-<env> --delete
aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"
```

## Environment Variables

### Frontend (.env.local)

```
VITE_API_BASE_URL=https://your-api-id.execute-api.eu-central-1.amazonaws.com/prod
VITE_COGNITO_USER_POOL_ID=eu-central-1_XXXXXXXXX
VITE_COGNITO_CLIENT_ID=your-client-id
VITE_COGNITO_DOMAIN=your-domain.auth.eu-central-1.amazoncognito.com
VITE_AWS_REGION=eu-central-1
```

## License

TBD
