# Development and Deployment Workflow

## Project Context

VocabTrainer is a serverless web application for 9th grade German Gymnasium students to practice French vocabulary by scanning workbook pages. The application uses AWS serverless architecture with Vue.js frontend, Python Lambda backend, DynamoDB database, and AI-powered OCR for vocabulary extraction.

## Technology Stack Summary

- **Frontend**: Vue 3 (Composition API), Tailwind CSS, Vite
- **Backend**: AWS Lambda (Python 3.11+), API Gateway
- **Database**: DynamoDB
- **Storage**: S3 for images and static site hosting
- **CDN**: CloudFront
- **Authentication**: AWS Cognito with OAuth2 flow
- **AI/OCR**: AWS Textract (primary), OpenAI Vision API (fallback)
- **Infrastructure**: AWS SAM or CloudFormation
- **Monitoring**: CloudWatch

## Development Environment Setup

### Prerequisites

1. Install required tools:
   - Node.js 18+ and npm
   - Python 3.11+
   - AWS CLI configured with appropriate credentials
   - AWS SAM CLI for local testing
   - Git for version control

2. Clone repository and install dependencies:
   ```bash
   # Frontend
   cd frontend
   npm install
   
   # Backend
   cd backend
   pip install -r requirements.txt -t ./dependencies
   ```

3. Environment configuration:
   - Create `.env` files for local development
   - Frontend needs: API Gateway URL, Cognito User Pool ID, Cognito Client ID
   - Backend needs: DynamoDB table names, S3 bucket names, AWS region

### Local Development Workflow

**Frontend Development:**

1. Run Vite dev server with hot reload:
   ```bash
   cd frontend
   npm run dev
   ```

2. Access at `http://localhost:5173`

3. Mock API responses during development using MSW (Mock Service Worker) or similar

4. Use Vue DevTools browser extension for debugging

**Backend Development:**

1. Use SAM local for Lambda testing:
   ```bash
   sam local start-api
   ```

2. Test individual Lambda functions:
   ```bash
   sam local invoke FunctionName -e events/test-event.json
   ```

3. Use DynamoDB Local for database testing:
   ```bash
   docker run -p 8000:8000 amazon/dynamodb-local
   ```

4. Configure Lambda functions to use local DynamoDB endpoint during testing

**Authentication Testing:**

1. Create test users in Cognito User Pool via AWS Console
2. Use Cognito hosted UI for OAuth flow testing
3. Store tokens in localStorage for session persistence
4. Implement token refresh logic before expiration

## Git Workflow and Branching Strategy

### Branch Structure

- `main` - production-ready code, protected branch
- `develop` - integration branch for features
- `feature/*` - individual feature branches
- `bugfix/*` - bug fix branches
- `hotfix/*` - urgent production fixes

### Commit Convention

Use conventional commits format:
- `feat:` - new feature
- `fix:` - bug fix
- `docs:` - documentation changes
- `style:` - formatting, missing semicolons, etc.
- `refactor:` - code restructuring
- `test:` - adding tests
- `chore:` - maintenance tasks

Example: `feat: add vocabulary extraction review interface`

### Pull Request Process

1. Create feature branch from `develop`
2. Implement feature with regular commits
3. Write/update tests
4. Update documentation if needed
5. Create PR to `develop` with description of changes
6. Address review feedback
7. Merge after approval (squash and merge preferred)

## Infrastructure as Code

### AWS SAM Template Structure

```
template.yaml          # Main SAM template
├── parameters/
│   ├── dev.json      # Development parameters
│   └── prod.json     # Production parameters
├── functions/
│   ├── upload/
│   ├── extraction/
│   ├── vocab-crud/
│   ├── practice/
│   └── progress/
└── layers/
    └── common/       # Shared dependencies
```

### Resource Naming Convention

Use consistent naming with environment prefix:
- `vocabtrainer-{env}-users-table`
- `vocabtrainer-{env}-images-bucket`
- `vocabtrainer-{env}-api`
- `vocabtrainer-{env}-user-pool`

### SAM Template Key Sections

**Globals:**
- Runtime: python3.11
- Timeout: 30 seconds (adjust per function)
- Memory: 512MB (adjust per function)
- Environment variables (DynamoDB tables, S3 buckets)
- Tracing: Active (X-Ray)
- Tags for cost tracking

**Cognito User Pool:**
- Email-based sign-up
- Password policy (min 8 chars, uppercase, lowercase, numbers)
- MFA optional
- OAuth2 flows enabled
- Hosted UI domain
- Callback URLs for dev and prod environments

**API Gateway:**
- REST API with CORS enabled
- Cognito authorizer configured
- Request validation enabled
- API key for rate limiting (optional)
- CloudWatch logging enabled

**Lambda Functions:**
- VPC configuration not needed (serverless services)
- IAM roles with least privilege
- Environment variables from SSM Parameter Store
- Reserved concurrency for critical functions
- Dead letter queue for failed invocations

**DynamoDB Tables:**
- On-demand billing mode (adjust if predictable traffic)
- Point-in-time recovery enabled
- Encryption at rest
- TTL enabled for PracticeSessions table (90 days)
- GSI for queries (userId-based lookups)

**S3 Buckets:**
- Versioning enabled for images bucket
- Lifecycle policy: delete after 1 year
- CORS configuration for frontend uploads
- Bucket policy for CloudFront access
- Server-side encryption (SSE-S3)

**CloudFront Distribution:**
- Origin: S3 static site bucket
- HTTPS only
- Caching strategy (cache static assets, not API calls)
- Custom domain (optional)
- WAF integration (optional, for DDoS protection)

## Deployment Pipeline

### Development Environment Deployment

**Manual deployment for testing:**

```bash
# Backend deployment
cd backend
sam build
sam deploy --config-env dev --guided

# Frontend deployment
cd frontend
npm run build
aws s3 sync dist/ s3://vocabtrainer-dev-frontend-bucket --delete
aws cloudfront create-invalidation --distribution-id XXX --paths "/*"
```

**What gets deployed:**
- All Lambda functions with dependencies
- DynamoDB tables (if not exists)
- S3 buckets
- API Gateway stages
- Cognito configuration
- CloudFront distribution

**Post-deployment verification:**
1. Check API Gateway endpoints are accessible
2. Test Cognito authentication flow
3. Verify DynamoDB tables created
4. Upload test image and trigger extraction
5. Run smoke tests on critical paths

### Production Environment Deployment

**Pre-deployment checklist:**
- All tests passing in develop branch
- Code review completed
- Security scan completed (e.g., Snyk, AWS Inspector)
- Documentation updated
- Changelog updated

**Deployment process:**

1. Merge `develop` to `main` via PR
2. Tag release with semantic version (e.g., `v1.0.0`)
3. Deploy backend:
   ```bash
   sam deploy --config-env prod --no-confirm-changeset
   ```
4. Deploy frontend:
   ```bash
   npm run build:prod
   aws s3 sync dist/ s3://vocabtrainer-prod-frontend-bucket --delete
   aws cloudfront create-invalidation --distribution-id YYY --paths "/*"
   ```

**Rollback procedure:**
1. Identify last stable version tag
2. Check out that tag
3. Deploy previous version using same deployment commands
4. Verify rollback successful
5. Investigate and fix issue in develop branch

### CI/CD Automation (Future Enhancement)

**GitHub Actions workflow:**

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main, develop]
    
jobs:
  test:
    - Run frontend tests (Vitest)
    - Run backend tests (pytest)
    - Run linting (ESLint, flake8)
    
  deploy-dev:
    if: branch == 'develop'
    - Deploy backend to dev
    - Deploy frontend to dev
    - Run smoke tests
    
  deploy-prod:
    if: branch == 'main'
    - Deploy backend to prod
    - Deploy frontend to prod
    - Run smoke tests
    - Notify team on Slack
```

## Testing Strategy

### Frontend Testing

**Unit Tests (Vitest):**
- Vue component logic
- Utility functions (answer matching, score calculation)
- Store actions and getters (Pinia)

**Component Tests (Vue Test Utils):**
- User interactions
- Props and events
- Conditional rendering
- Form validation

**E2E Tests (Cypress or Playwright):**
- Complete user flows: upload → review → practice
- Authentication flow
- Cross-browser compatibility (Chrome, Firefox, Safari)

**Test Coverage Goals:**
- Minimum 80% code coverage
- 100% coverage for critical paths (answer checking, score calculation)

### Backend Testing

**Unit Tests (pytest):**
- Lambda handler functions
- Business logic functions
- Data validation
- Error handling

**Integration Tests:**
- DynamoDB operations with DynamoDB Local
- S3 operations with LocalStack
- Textract mock responses
- API Gateway request/response mapping

**Load Tests (Locust or Artillery):**
- Simulate concurrent users
- Test Lambda scaling
- Identify performance bottlenecks
- Verify DynamoDB read/write capacity

### Test Data Management

**Test Images:**
- Create sample workbook images with known vocabulary
- Include edge cases: handwriting, poor quality, rotated images
- Store in `test/fixtures/images/`

**Expected Extraction Results:**
- JSON files with expected vocabulary pairs
- Used for validating extraction accuracy
- Store in `test/fixtures/expected-results/`

**Test Users:**
- Create dedicated test accounts in Cognito dev environment
- Document credentials in secure location (not in repo)
- Use separate Cognito User Pool for testing

## Monitoring and Logging

### CloudWatch Configuration

**Log Groups:**
- `/aws/lambda/vocabtrainer-{env}-{function-name}`
- Retention: 7 days for dev, 30 days for prod
- Log level: INFO for prod, DEBUG for dev

**Metrics to Track:**
- Lambda invocation count, duration, errors
- API Gateway 4xx and 5xx errors
- DynamoDB read/write capacity usage
- S3 bucket request count
- Cognito sign-up and sign-in count

**Alarms:**
- Lambda error rate > 5%
- API Gateway 5xx rate > 1%
- Lambda duration > 25 seconds (near timeout)
- DynamoDB throttled requests > 0
- Cognito user pool sign-in failures > 10/min

**Dashboards:**
- Overview dashboard: key metrics at a glance
- Performance dashboard: latency, duration, throughput
- Error dashboard: error rates, failed invocations

### X-Ray Tracing

Enable X-Ray for Lambda functions to trace:
- API Gateway → Lambda → DynamoDB flow
- Lambda → Textract API calls
- Identify slow operations
- Analyze cold start impact

### Application Logging Best Practices

**Structured Logging:**
```python
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_event(event_type, user_id, metadata):
    logger.info(json.dumps({
        'event_type': event_type,
        'user_id': user_id,
        'timestamp': datetime.utcnow().isoformat(),
        'metadata': metadata
    }))
```

**Log Key Events:**
- User authentication (success/failure)
- Image upload (size, format)
- Extraction start/complete (duration, item count)
- Practice session start/complete (score, duration)
- Errors with full context (request ID, user ID, error message)

**PII Handling:**
- Never log email addresses or passwords
- Hash or mask sensitive data
- Log user IDs only (Cognito sub)

## Security Best Practices

### IAM Policies

**Principle of Least Privilege:**
- Lambda execution roles have minimal permissions
- Separate roles per function
- No wildcard permissions in production

**Example Lambda Policy:**
```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:Query"
  ],
  "Resource": "arn:aws:dynamodb:region:account:table/vocabtrainer-prod-vocabsets-table"
}
```

### API Security

**Authentication:**
- All API endpoints require Cognito JWT token
- Token validation in API Gateway authorizer
- Token expiration: 1 hour (access token), 30 days (refresh token)

**Authorization:**
- Verify user owns resource before operations
- Check userId from JWT matches resource owner
- Implement in Lambda function logic

**Rate Limiting:**
- API Gateway usage plans with throttling
- Per-user rate limits: 100 requests/min
- Burst limit: 200 requests

**Input Validation:**
- Validate all input at API Gateway level (request validators)
- Secondary validation in Lambda functions
- Sanitize file names and paths
- Limit file upload size (10MB max)

### Data Protection

**Encryption at Rest:**
- DynamoDB tables encrypted with AWS managed keys
- S3 buckets encrypted with SSE-S3
- Consider KMS for additional control (higher cost)

**Encryption in Transit:**
- HTTPS only (enforce in CloudFront and API Gateway)
- TLS 1.2 minimum

**Data Retention:**
- Images deleted after 1 year (S3 lifecycle policy)
- Practice sessions TTL after 90 days (DynamoDB TTL)
- User data deleted on account closure

**Secrets Management:**
- Store API keys in AWS Secrets Manager or SSM Parameter Store
- Never commit secrets to repository
- Rotate secrets regularly
- Use environment-specific secrets

### Vulnerability Management

**Dependency Scanning:**
- Run `npm audit` for frontend dependencies
- Run `pip-audit` or `safety` for Python dependencies
- Address high/critical vulnerabilities immediately

**Code Scanning:**
- Use AWS CodeGuru for automated code review
- Run static analysis (SonarQube, ESLint security rules)
- Check for common vulnerabilities (XSS, SQL injection patterns)

**Penetration Testing:**
- Conduct before production launch
- Annual security audits
- Bug bounty program (optional)

## Cost Optimization

### AWS Cost Monitoring

**Cost Allocation Tags:**
- Environment (dev, prod)
- Project (vocabtrainer)
- Owner (team or individual)
- Cost center

**Budgets and Alerts:**
- Monthly budget per environment
- Alert at 80% and 100% of budget
- Forecast alerts for month-end overage

### Optimization Strategies

**Lambda:**
- Right-size memory allocation (test different sizes)
- Minimize cold starts (provisioned concurrency for critical functions)
- Optimize package size (layer for common dependencies)
- Short timeout for simple operations

**DynamoDB:**
- On-demand billing for unpredictable traffic
- Provisioned capacity if traffic is steady (cheaper)
- Use DynamoDB TTL to auto-delete old data
- Avoid expensive scans (use queries with indexes)

**S3:**
- Lifecycle policies to delete old images
- Use S3 Intelligent-Tiering for infrequently accessed objects
- Enable S3 Transfer Acceleration only if needed (higher cost)

**API Gateway:**
- Cache GET responses where appropriate
- Use regional endpoint (cheaper than edge-optimized)
- Monitor unused APIs and disable

**CloudFront:**
- Set appropriate TTL for static assets
- Use origin shield for high-traffic scenarios
- Minimize invalidations (cost per path)

### Development Cost Savings

**Dev Environment:**
- Use smaller DynamoDB capacity
- Delete dev environment when not in use
- Use LocalStack for local AWS testing
- Share dev environment among team members

## Operational Procedures

### Backup and Disaster Recovery

**DynamoDB Backups:**
- Point-in-time recovery enabled
- On-demand backups before major changes
- Cross-region backup for production (optional)
- Restore testing quarterly

**S3 Versioning:**
- Enabled on critical buckets
- Lifecycle policy to delete old versions after 30 days

**Infrastructure Backup:**
- SAM template in version control
- Export configuration from AWS Console as backup
- Document manual configuration steps

**Recovery Time Objective (RTO):**
- Target: 4 hours for production restore
- Procedure documented and tested

**Recovery Point Objective (RPO):**
- Target: 24 hours of data loss acceptable
- Point-in-time recovery provides better RPO

### Incident Response

**Severity Levels:**
- P1 (Critical): Service down, users cannot access
- P2 (High): Major feature broken, workaround available
- P3 (Medium): Minor feature issue
- P4 (Low): Cosmetic issue

**Incident Response Steps:**
1. Detect (alarms, user reports)
2. Assess severity
3. Notify stakeholders
4. Investigate (logs, metrics, traces)
5. Implement fix or rollback
6. Verify resolution
7. Post-mortem analysis
8. Update documentation

**Communication Plan:**
- Status page for user notifications (optional for single user)
- Slack/email for team notifications
- Regular updates during P1 incidents

### Maintenance Windows

**Scheduled Maintenance:**
- Deploy during low-traffic hours (late evening)
- Notify users 24 hours in advance (if multi-user)
- Database migrations during maintenance window
- Test rollback procedure before maintenance

**Emergency Maintenance:**
- Security patches deployed immediately
- Critical bug fixes outside normal window
- Extended testing in dev before production

## Documentation Requirements

### Code Documentation

**Frontend:**
- JSDoc comments for functions
- Component prop documentation
- README per major directory
- Storybook for UI components (optional)

**Backend:**
- Docstrings for Python functions
- API endpoint documentation (OpenAPI spec)
- Lambda function README with trigger and permissions
- Data model documentation

### Architecture Documentation

**Diagrams:**
- System architecture diagram (updated quarterly)
- Data flow diagrams
- Infrastructure diagram (AWS resources)
- Authentication flow diagram

**Decision Records:**
- Architecture Decision Records (ADRs) for major decisions
- Document why technology choices made
- Store in `docs/decisions/` directory

### Operational Documentation

**Runbooks:**
- Deployment procedure (this document)
- Rollback procedure
- Common troubleshooting steps
- Database migration process
- How to add new Lambda function
- How to update Cognito configuration

**User Documentation:**
- User guide (how to use the application)
- FAQ
- Troubleshooting guide for common errors
- Privacy policy
- Terms of service (if multi-user)

## Development Phases

### Phase 1: MVP Core (Weeks 1-2)

**Deliverables:**
- AWS infrastructure deployed (dev environment)
- User authentication working (Cognito)
- Image upload to S3
- Basic extraction with Textract
- Manual review interface for extracted vocabulary
- Simple practice interface (type answers)
- DynamoDB tables with basic data

**Success Criteria:**
- Single user can sign up, upload image, review extraction, and practice vocabulary
- No production deployment yet

### Phase 2: Polish and Progress (Weeks 3-4)

**Deliverables:**
- Progress tracking (correctness per word)
- Dashboard with vocabulary sets list
- Improved extraction accuracy (better parsing)
- Answer fuzzy matching (accept minor typos)
- Session history
- Basic charts (progress over time)

**Success Criteria:**
- User can track learning progress
- System handles common extraction errors gracefully

### Phase 3: Production Ready (Week 5)

**Deliverables:**
- Production environment deployed
- Security hardening (rate limiting, input validation)
- Monitoring and alarms configured
- Production testing completed
- User documentation written
- Backup and restore tested

**Success Criteria:**
- Application ready for real student use
- All production checklist items completed

### Phase 4: Enhancements (Future)

**Potential Features:**
- Spaced repetition algorithm
- Audio pronunciation (text-to-speech)
- Mobile app (React Native or PWA)
- Multiple language pairs (German-English, etc.)
- Vocabulary sharing between users
- Teacher accounts with student progress visibility
- Gamification (streaks, badges, leaderboards)
- Offline mode with sync

## Quality Gates

### Pre-Commit Checks

- Linting passes (ESLint, flake8)
- Formatting enforced (Prettier, Black)
- No console.log statements in code
- No commented-out code blocks
- Secrets not committed

### Pre-Merge Checks

- All tests passing
- Code coverage above threshold
- Code review approved by one reviewer
- No merge conflicts
- Branch up to date with target

### Pre-Deployment Checks

- All tests passing in target environment
- Security scan completed
- Performance testing completed
- Documentation updated
- Changelog entry added
- Rollback plan documented

### Post-Deployment Checks

- Smoke tests passing
- No alarms triggered
- Key metrics within normal range
- User acceptance testing completed
- Stakeholders notified

## Troubleshooting Guide

### Common Issues and Solutions

**Issue: Lambda timeout during extraction**
- Solution: Increase timeout to 60 seconds for extraction function
- Solution: Optimize Textract API call (use async if possible)
- Solution: Break large images into smaller sections

**Issue: Extraction accuracy poor**
- Solution: Preprocess image (increase contrast, deskew)
- Solution: Fall back to OpenAI Vision API for handwritten text
- Solution: Implement manual correction interface (already planned)

**Issue: Cognito authentication failing**
- Solution: Check callback URLs match environment
- Solution: Verify JWT token not expired
- Solution: Check CORS configuration in API Gateway

**Issue: DynamoDB throttling errors**
- Solution: Switch to on-demand billing
- Solution: Check for hot partition key
- Solution: Implement exponential backoff in Lambda

**Issue: S3 upload failing from frontend**
- Solution: Verify presigned URL not expired
- Solution: Check CORS configuration on bucket
- Solution: Verify file size under limit

**Issue: CloudFront serving stale content**
- Solution: Create invalidation for updated paths
- Solution: Review caching headers from S3
- Solution: Use cache busting for JS/CSS files (Vite handles this)

### Debug Checklist

1. Check CloudWatch logs for error messages
2. Review X-Ray traces for slow operations
3. Verify IAM permissions on Lambda role
4. Test API endpoint with Postman/curl
5. Check DynamoDB item exists with correct structure
6. Verify S3 object exists and accessible
7. Review recent deployments for changes
8. Check AWS service health dashboard

### Getting Help

- AWS Support (if subscribed)
- Stack Overflow for technical questions
- AWS Community Forums
- GitHub Issues for package-specific problems
- Team knowledge base (wiki/Notion/Confluence)

## Conclusion

This workflow document provides comprehensive guidance for developing, testing, deploying, and maintaining the VocabTrainer application. Follow these procedures to ensure consistent, high-quality releases with minimal downtime and optimal cost efficiency. Update this document as the project evolves and new patterns emerge.