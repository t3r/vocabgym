# Development & Deployment Workflow

## Project Context

VocabTrainer is a serverless web application for 9th grade German Gymnasium students learning French vocabulary. The application extracts vocabulary from scanned workbook images using AWS services and provides typing-based practice sessions.

**Core Technology Stack:**
- Frontend: Vue 3, Tailwind CSS, Vite
- Backend: AWS Lambda (Python 3.11+), API Gateway
- Database: DynamoDB
- Storage: S3
- Authentication: AWS Cognito with OAuth2 flow
- OCR: AWS Textract (primary), OpenAI Vision API (fallback)
- Infrastructure: AWS SAM or CloudFormation
- Hosting: CloudFront + S3 for static frontend

## Development Environment Setup

### Prerequisites

- Node.js 18+ and npm/yarn
- Python 3.11+
- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed
- Git for version control

### Local Development Setup

1. **Clone and Initialize Repository**
   - Create repository structure:
     ```
     vocabtrainer/
     ├── frontend/          # Vue application
     ├── backend/           # Lambda functions
     ├── infrastructure/    # SAM/CloudFormation templates
     ├── docs/             # Documentation
     └── README.md
     ```

2. **Frontend Setup**
   - Navigate to `frontend/` directory
   - Initialize Vue 3 project with Vite: `npm create vite@latest . -- --template vue`
   - Install dependencies: `npm install`
   - Install Tailwind CSS: `npm install -D tailwindcss postcss autoprefixer`
   - Initialize Tailwind: `npx tailwindcss init -p`
   - Install additional packages:
     - `npm install vue-router@4`
     - `npm install pinia`
     - `npm install axios`
     - `npm install @aws-amplify/auth` (for Cognito integration)
     - `npm install chart.js vue-chartjs` (for progress visualization)

3. **Backend Setup**
   - Navigate to `backend/` directory
   - Create virtual environment: `python -m venv venv`
   - Activate: `source venv/bin/activate` (Unix) or `venv\Scripts\activate` (Windows)
   - Create `requirements.txt`:
     ```
     boto3>=1.28.0
     aws-lambda-powertools>=2.20.0
     pydantic>=2.0.0
     python-jose[cryptography]>=3.3.0
     ```
   - Install dependencies: `pip install -r requirements.txt`

4. **Infrastructure Setup**
   - Navigate to `infrastructure/` directory
   - Initialize SAM application: `sam init`
   - Choose custom template location and Python runtime

### Environment Variables

Create `.env` files for local development:

**Frontend `.env.local`:**
```
VITE_API_GATEWAY_URL=https://your-api-id.execute-api.region.amazonaws.com/prod
VITE_COGNITO_USER_POOL_ID=your-user-pool-id
VITE_COGNITO_CLIENT_ID=your-client-id
VITE_COGNITO_DOMAIN=your-cognito-domain.auth.region.amazoncognito.com
VITE_AWS_REGION=eu-central-1
```

**Backend environment variables** (managed in SAM template):
- `DYNAMODB_USERS_TABLE`
- `DYNAMODB_VOCABSETS_TABLE`
- `DYNAMODB_VOCABITEMS_TABLE`
- `DYNAMODB_PRACTICE_TABLE`
- `DYNAMODB_PROGRESS_TABLE`
- `S3_IMAGES_BUCKET`
- `TEXTRACT_ROLE_ARN`
- `OPENAI_API_KEY` (stored in AWS Secrets Manager)

## Development Workflow

### Branch Strategy

Use Git Flow approach:
- `main` - production-ready code
- `develop` - integration branch for features
- `feature/*` - individual feature branches
- `hotfix/*` - urgent production fixes

### Feature Development Process

1. **Create Feature Branch**
   - Branch from `develop`: `git checkout -b feature/vocab-extraction develop`

2. **Frontend Development**
   - Run dev server: `npm run dev` (from `frontend/`)
   - Access at `http://localhost:5173`
   - Hot reload enabled for rapid iteration
   - Use Vue DevTools browser extension for debugging
   - Follow component structure:
     ```
     src/
     ├── components/     # Reusable UI components
     ├── views/         # Page-level components
     ├── stores/        # Pinia stores
     ├── router/        # Vue Router configuration
     ├── services/      # API service layer
     ├── utils/         # Helper functions
     └── assets/        # Static assets
     ```

3. **Backend Development**
   - Develop Lambda functions in `backend/functions/`
   - Each function in separate directory with `handler.py` and `requirements.txt`
   - Use AWS Lambda Powertools for logging, tracing, metrics
   - Local testing with SAM: `sam local start-api`
   - Access local API at `http://localhost:3000`
   - Use Postman or curl for API testing

4. **Testing Locally**
   - **Frontend unit tests**: `npm run test` (Vitest)
   - **Backend unit tests**: `pytest` in backend directory
   - **Integration testing**: Use SAM local with DynamoDB Local
   - **E2E testing**: Cypress or Playwright for critical user flows

5. **Code Quality**
   - **Frontend linting**: `npm run lint` (ESLint + Prettier)
   - **Backend linting**: `flake8` and `black` for formatting
   - **Type checking**: Use JSDoc comments in Vue or migrate to TypeScript
   - Pre-commit hooks with husky to enforce quality checks

### AWS Resource Provisioning

#### Initial Infrastructure Setup

1. **Create SAM Template** (`infrastructure/template.yaml`):
   ```yaml
   AWSTemplateFormatVersion: '2010-09-09'
   Transform: AWS::Serverless-2016-10-31
   
   Parameters:
     Environment:
       Type: String
       Default: dev
       AllowedValues: [dev, staging, prod]
   
   Resources:
     # Cognito User Pool
     UserPool:
       Type: AWS::Cognito::UserPool
       Properties:
         UserPoolName: !Sub VocabTrainer-${Environment}
         UsernameAttributes:
           - email
         AutoVerifiedAttributes:
           - email
         Schema:
           - Name: email
             Required: true
             Mutable: false
     
     # User Pool Client
     UserPoolClient:
       Type: AWS::Cognito::UserPoolClient
       Properties:
         ClientName: !Sub VocabTrainer-Client-${Environment}
         UserPoolId: !Ref UserPool
         GenerateSecret: false
         AllowedOAuthFlows:
           - code
         AllowedOAuthScopes:
           - openid
           - email
           - profile
         CallbackURLs:
           - http://localhost:5173/callback
           - !Sub https://${CloudFrontDistribution.DomainName}/callback
         LogoutURLs:
           - http://localhost:5173
           - !Sub https://${CloudFrontDistribution.DomainName}
     
     # DynamoDB Tables
     UsersTable:
       Type: AWS::DynamoDB::Table
       Properties:
         TableName: !Sub VocabTrainer-Users-${Environment}
         BillingMode: PAY_PER_REQUEST
         AttributeDefinitions:
           - AttributeName: userId
             AttributeType: S
         KeySchema:
           - AttributeName: userId
             KeyType: HASH
     
     VocabSetsTable:
       Type: AWS::DynamoDB::Table
       Properties:
         TableName: !Sub VocabTrainer-VocabSets-${Environment}
         BillingMode: PAY_PER_REQUEST
         AttributeDefinitions:
           - AttributeName: vocabSetId
             AttributeType: S
           - AttributeName: userId
             AttributeType: S
         KeySchema:
           - AttributeName: vocabSetId
             KeyType: HASH
           - AttributeName: userId
             KeyType: RANGE
         GlobalSecondaryIndexes:
           - IndexName: UserIdIndex
             KeySchema:
               - AttributeName: userId
                 KeyType: HASH
             Projection:
               ProjectionType: ALL
     
     # Continue with other tables...
     
     # S3 Bucket for Images
     ImagesBucket:
       Type: AWS::S3::Bucket
       Properties:
         BucketName: !Sub vocabtrainer-images-${Environment}-${AWS::AccountId}
         CorsConfiguration:
           CorsRules:
             - AllowedOrigins:
                 - '*'
               AllowedMethods:
                 - GET
                 - PUT
               AllowedHeaders:
                 - '*'
         LifecycleConfiguration:
           Rules:
             - Id: DeleteOldExtractionImages
               Status: Enabled
               ExpirationInDays: 90
     
     # API Gateway
     ApiGateway:
       Type: AWS::Serverless::Api
       Properties:
         StageName: !Ref Environment
         Auth:
           DefaultAuthorizer: CognitoAuthorizer
           Authorizers:
             CognitoAuthorizer:
               UserPoolArn: !GetAtt UserPool.Arn
         Cors:
           AllowOrigin: "'*'"
           AllowHeaders: "'*'"
           AllowMethods: "'GET,POST,PUT,DELETE,OPTIONS'"
     
     # Lambda Functions
     UploadHandlerFunction:
       Type: AWS::Serverless::Function
       Properties:
         CodeUri: ../backend/functions/upload_handler/
         Handler: handler.lambda_handler
         Runtime: python3.11
         Environment:
           Variables:
             S3_IMAGES_BUCKET: !Ref ImagesBucket
         Policies:
           - S3CrudPolicy:
               BucketName: !Ref ImagesBucket
         Events:
           Upload:
             Type: Api
             Properties:
               RestApiId: !Ref ApiGateway
               Path: /vocab/upload
               Method: POST
     
     # Continue with other Lambda functions...
   ```

2. **Deploy Infrastructure**
   ```bash
   cd infrastructure
   sam build
   sam deploy --guided --config-env dev
   ```
   - First deployment uses `--guided` to set parameters
   - Subsequent deploys: `sam deploy --config-env dev`
   - Creates `samconfig.toml` with saved configuration

3. **Retrieve Outputs**
   - After deployment, note outputs (API URL, Cognito IDs, etc.)
   - Update frontend `.env.local` with these values

### Deployment Pipeline

#### Manual Deployment Process (Initial/Development)

**Backend Deployment:**
```bash
cd infrastructure
sam build
sam deploy --config-env dev  # or staging, prod
```

**Frontend Deployment:**
```bash
cd frontend
npm run build
aws s3 sync dist/ s3://vocabtrainer-frontend-dev --delete
aws cloudfront create-invalidation --distribution-id XXXXX --paths "/*"
```

#### CI/CD Pipeline (GitHub Actions)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy VocabTrainer

on:
  push:
    branches:
      - main
      - develop
  pull_request:
    branches:
      - main
      - develop

env:
  AWS_REGION: eu-central-1

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Frontend Dependencies
        working-directory: frontend
        run: npm ci
      
      - name: Lint Frontend
        working-directory: frontend
        run: npm run lint
      
      - name: Test Frontend
        working-directory: frontend
        run: npm run test
      
      - name: Install Backend Dependencies
        working-directory: backend
        run: pip install -r requirements.txt -r requirements-dev.txt
      
      - name: Lint Backend
        working-directory: backend
        run: |
          flake8 .
          black --check .
      
      - name: Test Backend
        working-directory: backend
        run: pytest

  deploy-dev:
    needs: test
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    environment: development
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Setup SAM
        uses: aws-actions/setup-sam@v2
      
      - name: Build Backend
        working-directory: infrastructure
        run: sam build
      
      - name: Deploy Backend
        working-directory: infrastructure
        run: sam deploy --config-env dev --no-confirm-changeset --no-fail-on-empty-changeset
      
      - name: Get API Gateway URL
        id: get-api-url
        run: |
          API_URL=$(aws cloudformation describe-stacks \
            --stack-name vocabtrainer-dev \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
            --output text)
          echo "api_url=$API_URL" >> $GITHUB_OUTPUT
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Build Frontend
        working-directory: frontend
        env:
          VITE_API_GATEWAY_URL: ${{ steps.get-api-url.outputs.api_url }}
          VITE_COGNITO_USER_POOL_ID: ${{ secrets.DEV_COGNITO_USER_POOL_ID }}
          VITE_COGNITO_CLIENT_ID: ${{ secrets.DEV_COGNITO_CLIENT_ID }}
          VITE_COGNITO_DOMAIN: ${{ secrets.DEV_COGNITO_DOMAIN }}
          VITE_AWS_REGION: ${{ env.AWS_REGION }}
        run: |
          npm ci
          npm run build
      
      - name: Deploy Frontend to S3
        working-directory: frontend
        run: |
          aws s3 sync dist/ s3://vocabtrainer-frontend-dev --delete
      
      - name: Invalidate CloudFront
        run: |
          DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
            --stack-name vocabtrainer-dev \
            --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
            --output text)
          aws cloudfront create-invalidation \
            --distribution-id $DISTRIBUTION_ID \
            --paths "/*"

  deploy-prod:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      # Similar to deploy-dev but with prod configuration
      # Includes manual approval requirement via GitHub environments
```

#### Environment Strategy

Three environments with progressive deployment:
- **dev**: Auto-deploy from `develop` branch
- **staging**: Manual promotion from dev or auto-deploy from `release/*` branches
- **prod**: Manual promotion from staging, deploy from `main` branch with required approvals

### Database Migration Strategy

Since DynamoDB is schema-less, "migrations" are primarily about:
1. Adding new tables
2. Adding GSIs (Global Secondary Indexes)
3. Backfilling data

**Process:**
1. Update SAM template with new table/GSI definition
2. Deploy infrastructure changes (non-breaking for existing tables)
3. Write and run data migration script if needed:

```python
# scripts/migrate_add_mastery_level.py
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('VocabTrainer-Progress-dev')

# Scan all items and add default masteryLevel if missing
response = table.scan()
for item in response['Items']:
    if 'masteryLevel' not in item:
        table.update_item(
            Key={'PK': item['PK'], 'SK': item['SK']},
            UpdateExpression='SET masteryLevel = :level',
            ExpressionAttributeValues={':level': 0}
        )
```

4. Test migration in dev environment first
5. Run in staging, then production with monitoring

### Monitoring and Logging

#### CloudWatch Integration

**Lambda Functions:**
- All Lambda functions use AWS Lambda Powertools for structured logging
- Logs automatically sent to CloudWatch Logs
- Set up log retention policies: 7 days for dev, 30 days for prod

**Example logging setup in Lambda:**
```python
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="vocab-extraction")
tracer = Tracer(service="vocab-extraction")
metrics = Metrics(namespace="VocabTrainer", service="vocab-extraction")

@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context):
    logger.info("Processing vocabulary extraction", extra={"vocabSetId": vocab_set_id})
    
    try:
        # Processing logic
        metrics.add_metric(name="SuccessfulExtractions", unit=MetricUnit.Count, value=1)
    except Exception as e:
        logger.exception("Extraction failed")
        metrics.add_metric(name="FailedExtractions", unit=MetricUnit.Count, value=1)
        raise
```

**API Gateway:**
- Enable access logging to CloudWatch
- Log full requests/responses in dev, sanitized logs in prod

**Frontend Error Tracking:**
- Implement error boundary in Vue app
- Send critical errors to CloudWatch via API endpoint or use Sentry

#### Alarms and Notifications

Create CloudWatch Alarms for:
- Lambda error rate > 5%
- API Gateway 5xx errors > 10 in 5 minutes
- DynamoDB throttling events
- S3 bucket size exceeds threshold

Send notifications to SNS topic → email or Slack

**Example alarm in SAM template:**
```yaml
ExtractionErrorAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub VocabTrainer-ExtractionErrors-${Environment}
    MetricName: Errors
    Namespace: AWS/Lambda
    Statistic: Sum
    Period: 300
    EvaluationPeriods: 1
    Threshold: 5
    ComparisonOperator: GreaterThanThreshold
    Dimensions:
      - Name: FunctionName
        Value: !Ref ExtractionHandlerFunction
    AlarmActions:
      - !Ref AlertTopic
```

### Performance Optimization

#### Backend Optimization

1. **Lambda Cold Start Reduction:**
   - Keep function code small (< 50MB)
   - Use Lambda layers for shared dependencies
   - Consider provisioned concurrency for critical functions
   - Use ARM64 architecture for better price/performance

2. **DynamoDB Performance:**
   - Design partition keys to avoid hot partitions
   - Use batch operations where possible
   - Implement caching with ElastiCache or DAX for read-heavy tables (if needed)
   - Monitor consumed capacity and adjust on-demand/provisioned settings

3. **S3 Optimization:**
   - Use S3 Transfer Acceleration for faster uploads
   - Implement multipart upload for large images
   - Use appropriate storage class (Standard for active images)

4. **Textract Optimization:**
   - Process asynchronously for large documents
   - Cache extraction results in DynamoDB
   - Implement retry logic with exponential backoff

#### Frontend Optimization

1. **Build Optimization:**
   - Code splitting with Vue Router lazy loading
   - Tree shaking unused Tailwind classes (configured in `tailwind.config.js`)
   - Compress images and assets
   - Use Vite's built-in optimizations

2. **Runtime Optimization:**
   - Lazy load Chart.js only on progress page
   - Implement virtual scrolling for long vocabulary lists
   - Debounce search/filter inputs
   - Cache API responses in Pinia stores

3. **CloudFront Configuration:**
   - Enable compression (gzip/brotli)
   - Cache static assets with long TTL
   - Use cache policies for API responses where appropriate
   - Configure origin failover for high availability

### Security Best Practices

#### Authentication & Authorization

1. **Cognito Configuration:**
   - Enforce strong password policy
   - Enable MFA for production users (optional)
   - Set token expiration: access token 1 hour, refresh token 30 days
   - Use HTTPS-only for all OAuth redirects

2. **API Security:**
   - All endpoints require Cognito authentication except health checks
   - Validate JWT tokens in Lambda authorizer
   - Implement rate limiting via API Gateway usage plans
   - Use AWS WAF for production API Gateway

3. **Data Access:**
   - Lambda functions have minimal IAM permissions (principle of least privilege)
   - Users can only access their own data (enforce in Lambda logic)
   - Use pre-signed URLs with short expiration for S3 uploads

#### Data Protection

1. **Encryption:**
   - Enable S3 bucket encryption (SSE-S3 or SSE-KMS)
   - Enable DynamoDB encryption at rest
   - All data in transit uses TLS 1.2+

2. **Secrets Management:**
   - Store OpenAI API key in AWS Secrets Manager
   - Retrieve secrets in Lambda at runtime
   - Rotate secrets regularly

3. **Input Validation:**
   - Validate all user inputs in Lambda functions (use Pydantic models)
   - Sanitize uploaded filenames
   - Validate image file types and sizes
   - Protect against SQL injection (not applicable with DynamoDB, but validate for future RDS)

#### Compliance

- GDPR considerations: Users can delete their data
- Implement data retention policies
- Log access to sensitive data (CloudTrail)

### Rollback Procedures

#### Backend Rollback

If a deployment causes issues:

1. **Immediate rollback via SAM:**
   ```bash
   # List recent stack events
   aws cloudformation describe-stack-events --stack-name vocabtrainer-prod
   
   # Rollback to previous version
   aws cloudformation rollback-stack --stack-name vocabtrainer-prod
   ```

2. **Alternative: Redeploy previous version:**
   ```bash
   git checkout <previous-commit>
   cd infrastructure
   sam build
   sam deploy --config-env prod
   ```

#### Frontend Rollback

1. **Revert S3 content:**
   ```bash
   # S3 versioning should be enabled
   aws s3api list-object-versions --bucket vocabtrainer-frontend-prod
   # Restore previous version of each file
   ```

2. **Redeploy previous version:**
   ```bash
   git checkout <previous-commit>
   cd frontend
   npm run build
   aws s3 sync dist/ s3://vocabtrainer-frontend-prod --delete
   aws cloudfront create-invalidation --distribution-id XXXXX --paths "/*"
   ```

#### Database Rollback

DynamoDB changes are typically additive and non-breaking. If a migration causes issues:

1. Revert code changes that depend on new schema
2. Remove GSIs if they're causing throttling
3. Run reverse migration script to remove added attributes (rarely needed)

### Backup and Disaster Recovery

#### Automated Backups

1. **DynamoDB:**
   - Enable point-in-time recovery (PITR) for all tables
   - Schedule daily backups to S3 using AWS Backup
   - Retention: 7 days for dev, 30 days for prod

2. **S3:**
   - Enable versioning on images bucket
   - Configure cross-region replication for prod
   - Lifecycle policy to transition old versions to Glacier

3. **Infrastructure:**
   - SAM templates in Git serve as infrastructure backup
   - Export CloudFormation stacks regularly

#### Recovery Procedures

**Scenario: Complete region failure**

1. Deploy infrastructure to backup region using SAM
2. Restore DynamoDB tables from latest backup
3. Sync S3 data from replicated bucket
4. Update DNS/CloudFront to point to new region
5. Test thoroughly before announcing recovery

**Scenario: Accidental data deletion**

1. Identify timestamp of deletion from CloudWatch Logs
2. Use DynamoDB PITR to restore table to point before deletion
3. Or restore specific items from daily backup in S3

**RTO (Recovery Time Objective):** 4 hours
**RPO (Recovery Point Objective):** 1 hour (PITR granularity)

### Testing Strategy

#### Unit Testing

**Backend (Python):**
- Use pytest with moto for mocking AWS services
- Test each Lambda function handler independently
- Mock DynamoDB, S3, Textract responses
- Aim for 80% code coverage

```python
# tests/test_extraction_handler.py
import pytest
from moto import mock_dynamodb, mock_s3
from functions.extraction_handler import handler

@mock_dynamodb
@mock_s3
def test_extraction_success():
    # Setup mocks
    # Call handler
    # Assert results
    pass
```

**Frontend (Vue):**
- Use Vitest for unit testing
- Test components in isolation
- Mock API calls with MSW (Mock Service Worker)
- Test Pinia stores independently

```javascript
// tests/components/VocabCard.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import VocabCard from '@/components/VocabCard.vue'

describe('VocabCard', () => {
  it('renders German word correctly', () => {
    const wrapper = mount(VocabCard, {
      props: { german: 'Haus', french: 'maison' }
    })
    expect(wrapper.text()).toContain('Haus')
  })
})
```

#### Integration Testing

- Test complete user flows: upload → extract → review → practice
- Use SAM local to run backend locally with DynamoDB Local
- Frontend connects to local backend during integration tests
- Automated via GitHub Actions on pull requests

#### End-to-End Testing

Use Playwright or Cypress:
- Test authentication flow
- Test complete vocabulary lifecycle
- Test practice session with answer validation
- Run against staging environment before prod deployment

```javascript
// e2e/vocab-flow.spec.js
test('complete vocabulary flow', async ({ page }) => {
  await page.goto('/')
  await page.click('text=Login')
  // Authenticate
  await page.click('text=Upload Image')
  await page.setInputFiles('input[type="file"]', 'test-image.jpg')
  // Continue through flow
  await expect(page.locator('.success-message')).toBeVisible()
})
```

#### Load Testing

Use Locust or Artillery to test:
- API Gateway throughput
- Lambda concurrent executions
- DynamoDB read/write capacity
- Textract processing limits

Run load tests in staging environment before major releases.

### Documentation Maintenance

Keep documentation up-to-date as the project evolves:

1. **README.md** - Project overview, quick start, links to other docs
2. **Architecture Decision Records (ADRs)** - Document significant technical decisions
3. **API Documentation** - OpenAPI/Swagger spec for all endpoints
4. **Runbooks** - Step-by-step guides for common operational tasks
5. **Deployment Guide** - Detailed deployment instructions (this document)
6. **Troubleshooting Guide** - Common issues and solutions

Store all documentation in the `/docs` directory, version-controlled with code.

### Dependency Management

#### Frontend Dependencies

- Review and update dependencies monthly: `npm outdated`
- Update non-breaking changes: `npm update`
- Test major version updates in feature branch first
- Use Dependabot or Renovate for automated PR creation

#### Backend Dependencies

- Pin exact versions in `requirements.txt`
- Update dependencies quarterly after testing
- Check for security vulnerabilities: `pip-audit`
- Test Lambda runtime updates in dev before applying to prod

#### AWS Service Updates

- Subscribe to AWS service announcements
- Review Lambda runtime deprecation notices
- Plan migrations well in advance of EOL dates
- Test new features in dev environment first

### Cost Optimization

Monitor AWS costs and optimize:

1. **Right-size resources:**
   - Review Lambda memory allocations monthly
   - Monitor DynamoDB consumed capacity vs provisioned
   - Use S3 Intelligent-Tiering for images

2. **Use cost allocation tags:**
   - Tag all resources with Environment, Project, Owner
   - Enable cost allocation tags in AWS Billing
   - Review Cost Explorer monthly

3. **Set up billing alarms:**
   - Alert when monthly costs exceed threshold
   - Track costs per environment

4. **Optimize based on usage:**
   - If dev environment unused on weekends, automate shutdown
   - Archive old vocabulary sets to S3 Glacier
   - Implement cleanup Lambda to delete orphaned resources

### Handoff and Knowledge Transfer

For team onboarding or project handoff:

1. **Provide access:**
   - AWS account with appropriate IAM roles
   - GitHub repository access
   - Documentation links

2. **Walkthrough sessions:**
   - Architecture overview (30 min)
   - Local development setup (1 hour)
   - Deployment process (30 min)
   - Troubleshooting common issues (30 min)

3. **Pair programming:**
   - Implement a small feature together
   - Deploy to dev environment together

4. **Documentation quiz:**
   - Ensure new team member can navigate docs
   - Can deploy independently after training

This comprehensive workflow ensures consistent, reliable development and deployment processes throughout the project lifecycle.