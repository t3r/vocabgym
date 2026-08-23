# AWS Serverless Architecture and Implementation

## Project Context

VocabTrainer is a web-based French vocabulary learning application for 9th grade German Gymnasium students. The application allows students to scan workbook pages containing vocabulary tables, automatically extract the vocabulary using AI/OCR, and practice through typing-based exercises. The entire infrastructure runs on AWS using serverless architecture.

## Architecture Overview

### High-Level Architecture

```
User Browser
    ↓
CloudFront CDN (Frontend Distribution)
    ↓
S3 Bucket (Static Website)
    ↓
API Gateway (REST API)
    ↓
AWS Lambda Functions (Python 3.11+)
    ↓
├── DynamoDB (Data Storage)
├── S3 (Image Storage)
├── AWS Textract (OCR Processing)
├── Cognito User Pools (Authentication)
└── CloudWatch (Logging & Monitoring)
```

### Design Principles

1. **Serverless First**: Use managed services to minimize operational overhead
2. **Pay-per-use**: No fixed costs, scale to zero when not in use
3. **Security by Default**: Least privilege IAM roles, encrypted storage
4. **Stateless Functions**: Each Lambda invocation is independent
5. **Event-driven**: Asynchronous processing where possible

## AWS Services Configuration

### Amazon Cognito

**Purpose**: User authentication and authorization using OAuth 2.0 flow

**Configuration**:
- User Pool with hosted UI for login/signup
- Email as username
- Password requirements: minimum 8 characters, uppercase, lowercase, numbers
- MFA: Optional (can enable later)
- Email verification required
- OAuth 2.0 flows: Authorization code grant
- Callback URLs: `https://yourdomain.com/callback`, `http://localhost:5173/callback` (dev)
- Scopes: `openid`, `profile`, `email`
- Token validity: Access token 1 hour, Refresh token 30 days

**User Pool Structure**:
- Standard attributes: email, given_name, family_name
- Custom attributes: none initially (can add later if needed)
- Lambda triggers: none initially

**App Client Configuration**:
- Enable username/password auth
- Enable SRP auth flow
- Generate client secret: No (for public web client)
- Enable OAuth 2.0: Yes
- Allowed OAuth flows: Authorization code grant
- Allowed OAuth scopes: openid, profile, email

### Amazon S3

**Bucket 1: Static Website Hosting (Frontend)**
- Bucket name: `vocabtrainer-frontend-[region]-[account-id]`
- Purpose: Host Vue.js application
- Configuration:
  - Static website hosting enabled
  - Index document: `index.html`
  - Error document: `index.html` (for SPA routing)
  - Block public access: Off (served via CloudFront)
  - Bucket policy: Allow CloudFront OAI only
  - CORS: Not needed (same origin via CloudFront)

**Bucket 2: User Uploaded Images**
- Bucket name: `vocabtrainer-images-[region]-[account-id]`
- Purpose: Store workbook page scans
- Configuration:
  - Block public access: On
  - Encryption: SSE-S3 (AES-256)
  - Versioning: Disabled
  - Lifecycle policy:
    - Delete images older than 90 days (after extraction complete)
    - Transition to Glacier after 30 days if retention needed
  - CORS configuration:
```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["PUT", "POST"],
    "AllowedOrigins": ["https://yourdomain.com", "http://localhost:5173"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

**Folder Structure**:
```
/images/{userId}/{vocabSetId}/{timestamp}-original.{ext}
```

### Amazon DynamoDB

**Table Design Philosophy**:
- Single-table design not required (simpler multi-table approach for this scale)
- On-demand billing mode initially
- Evaluate provisioned capacity if usage patterns become predictable

**Table 1: Users**
```
Table Name: VocabTrainer-Users
Primary Key: userId (String) - Partition Key (Cognito sub)
Attributes:
  - userId: String (PK)
  - email: String
  - displayName: String
  - createdAt: Number (Unix timestamp)
  - lastLoginAt: Number (Unix timestamp)
  - preferences: Map
    - defaultDirection: String (de-to-fr | fr-to-de)
    - theme: String (light | dark)
    
Indexes: None required
Billing: On-demand
Encryption: AWS managed key
Point-in-time recovery: Enabled
TTL: Not applicable
```

**Table 2: VocabSets**
```
Table Name: VocabTrainer-VocabSets
Primary Key: 
  - vocabSetId (String) - Partition Key (UUID)
  - userId (String) - Sort Key
  
Attributes:
  - vocabSetId: String (PK)
  - userId: String (SK)
  - title: String
  - sourceImageKey: String (S3 key)
  - extractionStatus: String (pending | processing | review | approved)
  - metadata: Map
    - chapter: String
    - pageNumber: Number
    - topic: String
    - tags: List<String>
  - createdAt: Number
  - updatedAt: Number
  - itemCount: Number
  - rawExtractionData: String (JSON, optional - for debugging)

GSI-1:
  Name: UserVocabSetsIndex
  Partition Key: userId
  Sort Key: createdAt
  Projection: ALL
  
Billing: On-demand
```

**Table 3: VocabItems**
```
Table Name: VocabTrainer-VocabItems
Primary Key:
  - vocabSetId (String) - Partition Key
  - itemId (String) - Sort Key (UUID)
  
Attributes:
  - vocabSetId: String (PK)
  - itemId: String (SK)
  - german: String
  - french: String
  - notes: String (optional)
  - order: Number (display order)
  - createdAt: Number
  - updatedAt: Number
  - isActive: Boolean (for soft delete)
  
Indexes: None required (always queried by vocabSetId)
Billing: On-demand
```

**Table 4: PracticeSessions**
```
Table Name: VocabTrainer-PracticeSessions
Primary Key:
  - userId (String) - Partition Key
  - sessionId (String) - Sort Key (timestamp-UUID)
  
Attributes:
  - userId: String (PK)
  - sessionId: String (SK)
  - vocabSetId: String
  - startedAt: Number
  - completedAt: Number
  - totalQuestions: Number
  - correctAnswers: Number
  - score: Number (percentage)
  - duration: Number (seconds)
  - direction: String (de-to-fr | fr-to-de)
  - detailedResults: List<Map>
    [
      {
        itemId: String,
        german: String,
        french: String,
        userAnswer: String,
        correct: Boolean,
        attemptedAt: Number
      }
    ]

GSI-1:
  Name: VocabSetSessionsIndex
  Partition Key: vocabSetId
  Sort Key: completedAt
  Projection: ALL
  
Billing: On-demand
TTL: completedAt + 1 year (archive old sessions)
```

**Table 5: Progress**
```
Table Name: VocabTrainer-Progress
Primary Key:
  - compositeKey (String) - Partition Key (userId#vocabSetId)
  - itemId (String) - Sort Key
  
Attributes:
  - compositeKey: String (PK)
  - itemId: String (SK)
  - userId: String
  - vocabSetId: String
  - correctCount: Number
  - incorrectCount: Number
  - lastPracticedAt: Number
  - masteryLevel: Number (0-5, calculated field)
  - firstSeenAt: Number
  - streakCount: Number (consecutive correct)
  
Billing: On-demand
```

### AWS Lambda Functions

**Runtime Configuration**:
- Runtime: Python 3.11
- Architecture: arm64 (Graviton2 - better price/performance)
- Memory: 256 MB (adjust per function based on profiling)
- Timeout: 30 seconds (standard), 5 minutes (extraction)
- Environment variables:
  - `DYNAMODB_REGION`
  - `S3_BUCKET_IMAGES`
  - `COGNITO_USER_POOL_ID`
  - `LOG_LEVEL` (INFO | DEBUG)

**Lambda Layer**:
- Shared dependencies layer containing:
  - boto3 (latest)
  - python-dotenv
  - Pillow (image manipulation)
  - Custom utility modules (auth, validation, error handling)

**Function 1: upload_handler**
```
Handler: upload_handler.lambda_handler
Purpose: Generate S3 presigned URL for image upload
Memory: 256 MB
Timeout: 10 seconds

IAM Permissions:
  - s3:PutObject (vocabtrainer-images-* bucket)
  - dynamodb:PutItem (VocabSets table)
  - logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents

Trigger: API Gateway POST /vocab/upload

Input:
{
  "fileName": "workbook_page.jpg",
  "contentType": "image/jpeg"
}

Output:
{
  "uploadUrl": "https://...",
  "vocabSetId": "uuid",
  "imageKey": "images/userId/vocabSetId/timestamp-original.jpg",
  "expiresIn": 300
}

Logic:
1. Validate user authentication (Cognito JWT)
2. Generate vocabSetId (UUID)
3. Construct S3 key
4. Generate presigned POST URL (5 min expiry)
5. Create initial VocabSet record (status: pending)
6. Return presigned URL to client
```

**Function 2: extraction_handler**
```
Handler: extraction_handler.lambda_handler
Purpose: Process uploaded image with Textract and extract vocabulary
Memory: 512 MB
Timeout: 300 seconds (5 minutes)

IAM Permissions:
  - s3:GetObject (vocabtrainer-images-* bucket)
  - textract:AnalyzeDocument
  - dynamodb:UpdateItem (VocabSets table)
  - dynamodb:BatchWriteItem (VocabItems table)
  - logs:*

Trigger: API Gateway POST /vocab/process or S3 Event Notification

Input:
{
  "vocabSetId": "uuid",
  "userId": "cognito-sub"
}

Logic:
1. Update VocabSet status to 'processing'
2. Retrieve image from S3
3. Call Textract AnalyzeDocument with TABLES feature
4. Parse Textract response:
   - Identify table structures
   - Extract cells
   - Determine German/French columns (heuristics or ML)
   - Handle merged cells, headers, annotations
5. Structure vocabulary pairs:
   - Validate language detection (basic check)
   - Clean text (remove extra whitespace, normalize)
   - Assign order numbers
6. Store items in VocabItems table (batch write)
7. Update VocabSet (status: review, itemCount)
8. Store raw Textract JSON for debugging (optional)
9. Return extraction results

Textract Configuration:
  - FeatureTypes: ["TABLES"]
  - If handwriting detected: Add ["FORMS"] for better accuracy

Fallback Strategy:
  - If Textract confidence < 80%: Flag for manual review
  - If table structure unclear: Use OpenAI Vision API as fallback
  - Implement retry logic with exponential backoff
```

**Function 3: vocab_crud_handler**
```
Handler: vocab_crud_handler.lambda_handler
Purpose: CRUD operations on vocabulary sets and items
Memory: 256 MB
Timeout: 30 seconds

IAM Permissions:
  - dynamodb:GetItem, Query, PutItem, UpdateItem, DeleteItem
  - All VocabTrainer tables

Trigger: API Gateway multiple routes

Routes Handled:
  - GET /vocab - List all vocab sets for user
  - GET /vocab/{vocabSetId} - Get specific vocab set with items
  - PUT /vocab/{vocabSetId} - Update vocab set metadata or approve
  - DELETE /vocab/{vocabSetId} - Delete vocab set and items
  - PUT /vocab/{vocabSetId}/items/{itemId} - Update single item
  - POST /vocab/{vocabSetId}/items - Add item manually
  - DELETE /vocab/{vocabSetId}/items/{itemId} - Delete item

Authorization:
  - Validate user owns the vocabSetId
  - Extract userId from Cognito JWT claims

Key Operations:
1. List vocab sets: Query GSI-1 by userId, sort by createdAt DESC
2. Get vocab set: Parallel DynamoDB queries (metadata + items)
3. Approve vocab set: Update status to 'approved'
4. Delete: Transaction to delete VocabSet + all VocabItems
```

**Function 4: practice_handler**
```
Handler: practice_handler.lambda_handler
Purpose: Manage practice sessions - start, submit answers, complete
Memory: 256 MB
Timeout: 30 seconds

IAM Permissions:
  - dynamodb:Query, PutItem, UpdateItem
  - VocabItems, PracticeSessions, Progress tables

Trigger: API Gateway multiple routes

Routes:
  - POST /practice/start
  - POST /practice/submit
  - POST /practice/complete

Start Practice Logic:
Input:
{
  "vocabSetId": "uuid",
  "direction": "de-to-fr" | "fr-to-de",
  "count": 20  // optional, default all
}

1. Query VocabItems by vocabSetId
2. Shuffle items (Fisher-Yates)
3. Limit to count if specified
4. Create session record (PracticeSessions)
5. Return questions:
{
  "sessionId": "uuid",
  "questions": [
    {
      "itemId": "uuid",
      "question": "das Haus",  // or French word
      "order": 1
    }
  ]
}

Submit Answer Logic:
Input:
{
  "sessionId": "uuid",
  "itemId": "uuid",
  "answer": "la maison"
}

1. Retrieve correct answer from VocabItems
2. Normalize both answers (lowercase, trim, remove accents option)
3. Check exact match first
4. Apply fuzzy matching (Levenshtein distance ≤ 2 for minor typos)
5. Return immediate feedback:
{
  "correct": true,
  "correctAnswer": "la maison",
  "userAnswer": "la maison"
}
6. Update in-memory session state (don't write to DB yet)

Complete Session Logic:
Input:
{
  "sessionId": "uuid",
  "results": [
    {
      "itemId": "uuid",
      "correct": true,
      "userAnswer": "la maison"
    }
  ]
}

1. Calculate statistics (score, duration)
2. Write PracticeSession record with detailed results
3. Update Progress table for each item:
   - Increment correctCount or incorrectCount
   - Update lastPracticedAt
   - Recalculate masteryLevel
   - Update streak
4. Return summary:
{
  "score": 85,
  "correct": 17,
  "total": 20,
  "duration": 245
}
```

**Function 5: progress_handler**
```
Handler: progress_handler.lambda_handler
Purpose: Retrieve progress statistics and analytics
Memory: 256 MB
Timeout: 30 seconds

IAM Permissions:
  - dynamodb:Query
  - Progress, PracticeSessions tables

Trigger: API Gateway GET requests

Routes:
  - GET /progress/overview
  - GET /progress/{vocabSetId}
  - GET /progress/recent-sessions

Overview Logic:
1. Query all Progress records for user
2. Aggregate statistics:
   - Total words practiced
   - Overall mastery distribution
   - Words needing review (low mastery)
3. Query recent PracticeSessions (last 10)
4. Return dashboard data

VocabSet Progress Logic:
1. Query Progress by compositeKey (userId#vocabSetId)
2. Calculate per-item statistics
3. Identify struggling words (correctCount < incorrectCount)
4. Return detailed breakdown
```

**Function 6: authorizer**
```
Handler: authorizer.lambda_handler
Purpose: Custom API Gateway authorizer for Cognito JWT validation
Memory: 128 MB
Timeout: 10 seconds

IAM Permissions:
  - None (only validates tokens)

Logic:
1. Extract Bearer token from Authorization header
2. Verify JWT signature using Cognito JWKS
3. Validate token claims (exp, iss, aud)
4. Extract userId from 'sub' claim
5. Generate IAM policy:
   - Allow if valid
   - Deny if invalid
6. Attach userId to context (available in subsequent Lambda functions)

Caching: Enable API Gateway authorizer caching (5 minutes TTL)
```

### API Gateway Configuration

**API Type**: REST API (not HTTP API, for more control)

**Stage**: 
- Development: `dev`
- Production: `prod`

**Endpoints**:

```
POST   /vocab/upload
POST   /vocab/process
GET    /vocab
GET    /vocab/{vocabSetId}
PUT    /vocab/{vocabSetId}
DELETE /vocab/{vocabSetId}
PUT    /vocab/{vocabSetId}/items/{itemId}
POST   /vocab/{vocabSetId}/items
DELETE /vocab/{vocabSetId}/items/{itemId}

POST   /practice/start
POST   /practice/submit
POST   /practice/complete

GET    /progress/overview
GET    /progress/{vocabSetId}
GET    /progress/recent-sessions
```

**CORS Configuration** (for all endpoints):
```json
{
  "Access-Control-Allow-Origin": "https://yourdomain.com",
  "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
  "Access-Control-Max-Age": "3600"
}
```

**Authorization**:
- All endpoints except OPTIONS require Cognito JWT
- Use custom Lambda authorizer or Cognito User Pool authorizer
- Authorization header: `Bearer {token}`

**Request Validation**:
- Enable request validation models
- Reject requests with invalid bodies early (save Lambda costs)

**Throttling**:
- Default: 10,000 requests per second, burst 5,000
- Per-user: 100 requests per second (configurable)

**API Key**: Not required (using Cognito authentication)

**CloudWatch Integration**:
- Enable detailed metrics
- Log full requests/responses in dev
- Log errors only in prod

### AWS Textract Integration

**Service**: Amazon Textract

**API**: AnalyzeDocument (synchronous for < 1 page)

**Configuration**:
```python
textract_client.analyze_document(
    Document={
        'S3Object': {
            'Bucket': bucket_name,
            'Name': image_key
        }
    },
    FeatureTypes=['TABLES', 'FORMS']  # FORMS for handwriting
)
```

**Response Parsing Strategy**:

1. **Identify Tables**:
   - Look for `BlockType == 'TABLE'`
   - Each table has CELL children
   - Cells have RowIndex and ColumnIndex

2. **Extract Cell Content**:
   - Traverse relationships to get CHILD blocks
   - Concatenate WORD blocks within each cell
   - Maintain cell position mapping

3. **Determine Language Columns**:
   - Heuristic 1: Check header row for "Deutsch", "Französisch", "German", "French"
   - Heuristic 2: Use language detection on first 3 rows (boto3 comprehend)
   - Heuristic 3: Assume column order (configurable)
   - Store column mapping in metadata

4. **Handle Edge Cases**:
   - Merged cells: Use rowSpan/columnSpan
   - Headers: Skip first row if detected as header
   - Annotations: Separate from main table (OCR as notes)
   - Multiple tables: Process each separately or merge if continuation

5. **Confidence Thresholds**:
   - Overall confidence < 80%: Flag for review
   - Per-word confidence < 60%: Highlight in review interface
   - Store confidence scores in rawExtractionData

**Fallback: OpenAI Vision API**:
- If Textract fails or confidence too low
- Use GPT-4 Vision with prompt:
```
Extract the German-French vocabulary pairs from this workbook table image.
Return JSON format:
[
  {"german": "...", "french": "...", "notes": "..."},
  ...
]
Preserve all entries. If handwriting is unclear, mark with [?].
```

### CloudFront Configuration

**Purpose**: CDN for frontend, improves performance globally

**Origin**: S3 static website bucket

**Configuration**:
- Origin Protocol Policy: HTTPS only
- Viewer Protocol Policy: Redirect HTTP to HTTPS
- Allowed HTTP Methods: GET, HEAD, OPTIONS
- Cached HTTP Methods: GET, HEAD
- Compress Objects Automatically: Yes
- Price Class: Use Only U.S., Canada and Europe (adjust as needed)

**Cache Behavior**:
- Default TTL: 86400 (1 day)
- Min TTL: 0
- Max TTL: 31536000 (1 year)
- Cache based on:
  - Headers: None
  - Query strings: None (SPA handles routing)
  - Cookies: None

**Custom Error Responses**:
- 403, 404 → 200 /index.html (SPA routing)

**SSL Certificate**: 
- Use AWS Certificate Manager (ACM)
- Request certificate for custom domain
- Validate via DNS (Route 53)

**Domain Configuration**:
- Alternate Domain Names (CNAMEs): `app.yourdomain.com`
- Route 53 Alias record pointing to CloudFront distribution

### CloudWatch Configuration

**Lambda Logs**:
- Log group per function: `/aws/lambda/{function-name}`
- Retention: 7 days (dev), 30 days (prod)
- Log level: INFO (prod), DEBUG (dev)

**Structured Logging Format** (Python):
```python
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_event(level, message, **kwargs):
    log_entry = {
        'level': level,
        'message': message,
        'timestamp': datetime.utcnow().isoformat(),
        **kwargs
    }
    logger.info(json.dumps(log_entry))
```

**Key Metrics to Track**:
1. Lambda invocations per function
2. Lambda errors per function
3. Lambda duration (p50, p90, p99)
4. API Gateway 4XX errors
5. API Gateway 5XX errors
6. API Gateway latency
7. DynamoDB consumed read/write capacity
8. DynamoDB throttled requests
9. S3 upload success rate
10. Textract API errors

**CloudWatch Alarms**:
- Lambda error rate > 5% for 5 minutes
- API Gateway 5XX rate > 1% for 5 minutes
- DynamoDB throttling occurs
- Textract quota approaching limit
- Any function timeout

**Dashboards**:
- Create CloudWatch dashboard with:
  - API request volume graph
  - Lambda invocation counts
  - Error rates by function
  - Average latency trends
  - Cost estimate widget

### Infrastructure as Code

**Tool**: AWS SAM (Serverless Application Model)

**Project Structure**:
```
/infrastructure
  template.yaml          # Main SAM template
  /functions
    /upload_handler
      requirements.txt
      handler.py
    /extraction_handler
      requirements.txt
      handler.py
      textract_parser.py
    /vocab_crud_handler
      requirements.txt
      handler.py
    /practice_handler
      requirements.txt
      handler.py
      answer_checker.py
    /progress_handler
      requirements.txt
      handler.py
    /authorizer
      requirements.txt
      handler.py
  /layers
    /shared
      requirements.txt   # boto3, Pillow, etc.
      /python
        /lib
          utils.py       # Shared utilities
          auth.py
          validation.py
  samconfig.toml         # SAM CLI configuration
```

**SAM Template Sections**:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues:
      - dev
      - prod
  
  DomainName:
    Type: String
    Default: app.yourdomain.com

Globals:
  Function:
    Runtime: python3.11
    Architecture: arm64
    Timeout: 30
    MemorySize: 256
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        LOG_LEVEL: INFO
        DYNAMODB_REGION: !Ref AWS::Region
    Layers:
      - !Ref SharedLayer

Resources:
  # Cognito User Pool
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub VocabTrainer-${Environment}
      # ... configuration details

  # S3 Buckets
  FrontendBucket:
    Type: AWS::S3::Bucket
    # ... configuration

  ImagesBucket:
    Type: AWS::S3::Bucket
    # ... configuration

  # DynamoDB Tables
  UsersTable:
    Type: AWS::DynamoDB::Table
    # ... configuration

  # Lambda Functions
  UploadFunction:
    Type: AWS::Serverless::Function
    # ... configuration

  # API Gateway
  VocabTrainerApi:
    Type: AWS::Serverless::Api
    # ... configuration

  # CloudFront Distribution
  FrontendDistribution:
    Type: AWS::CloudFront::Distribution
    # ... configuration

Outputs:
  ApiEndpoint:
    Value: !Sub https://${VocabTrainerApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}
  
  CloudFrontUrl:
    Value: !GetAtt FrontendDistribution.DomainName
  
  UserPoolId:
    Value: !Ref UserPool
```

**Deployment Commands**:
```bash
# Build
sam build

# Validate template
sam validate

# Deploy to dev
sam deploy --config-env dev

# Deploy to prod
sam deploy --config-env prod --guided
```

## Security Implementation

### IAM Roles and Policies

**Principle**: Least privilege - each Lambda function has minimal required permissions

**Lambda Execution Roles**:

1. **UploadHandlerRole**:
   - S3: PutObject on images bucket (scoped to user's path)
   - DynamoDB: PutItem on VocabSets table
   - CloudWatch Logs: Write

2. **ExtractionHandlerRole**:
   - S3: GetObject on images bucket
   - Textract: AnalyzeDocument
   - DynamoDB: UpdateItem (VocabSets), BatchWriteItem (VocabItems)
   - CloudWatch Logs: Write

3. **VocabCrudHandlerRole**:
   - DynamoDB: GetItem, Query, PutItem, UpdateItem, DeleteItem (all tables)
   - CloudWatch Logs: Write

4. **PracticeHandlerRole**:
   - DynamoDB: Query, PutItem, UpdateItem (VocabItems, PracticeSessions, Progress)
   - CloudWatch Logs: Write

5. **ProgressHandlerRole**:
   - DynamoDB: Query (Progress, PracticeSessions)
   - CloudWatch Logs: Write

6. **AuthorizerRole**:
   - No AWS service permissions needed
   - CloudWatch Logs: Write

**S3 Bucket Policies**:

Images Bucket:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowLambdaRead",
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::vocabtrainer-images-*/*",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "YOUR_ACCOUNT_ID"
        }
      }
    },
    {
      "Sid": "AllowPresignedPut",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::vocabtrainer-images-*/images/*",
      "Condition": {
        "StringLike": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    }
  ]
}
```

### Encryption

**Data at Rest**:
- DynamoDB: AWS managed encryption (KMS)
- S3: SSE-S3 (AES-256) for images
- CloudWatch Logs: Encrypted by default

**Data in Transit**:
- All API calls: HTTPS only (enforced by API Gateway)
- CloudFront: TLS 1.2 minimum
- Internal AWS service calls: Encrypted by AWS

**Sensitive Data Handling**:
- User passwords: Never stored (Cognito handles)
- JWT tokens: Short-lived, httpOnly cookies where possible
- No PII in logs (sanitize before logging)

### Input Validation

**API Gateway Request Validation**:
- Define JSON schemas for request bodies
- Validate before Lambda invocation
- Return 400 Bad Request if invalid

**Lambda Function Validation**:
- Sanitize all user inputs
- Check parameter types and ranges
- Validate vocabSetId/itemId ownership
- Escape special characters for DynamoDB queries

**File Upload Validation**:
- Max file size: 10 MB
- Allowed MIME types: image/jpeg, image/png, image/heic
- Scan for malware (optional: integrate ClamAV or AWS GuardDuty)

### Authentication Flow

**User Sign-up/Sign-in**:
1. User clicks "Login" → redirected to Cognito hosted UI
2. User authenticates → Cognito returns authorization code
3. Frontend exchanges code for tokens (access, ID, refresh)
4. Store tokens securely (localStorage with expiry check)
5. Include access token in Authorization header for API calls

**Token Refresh**:
- Access token expires after 1 hour
- Use refresh token to get new access token
- Implement automatic refresh in frontend interceptor

**API Authorization**:
1. API Gateway receives request with Bearer token
2. Lambda authorizer validates token
3. If valid, allow request and pass userId to Lambda
4. Lambda checks resource ownership (userId matches)

## Performance Optimization

### Lambda Optimization

**Cold Start Mitigation**:
- Use arm64 architecture (faster cold starts)
- Minimize dependencies (use layers wisely)
- Consider provisioned concurrency for critical functions (cost vs benefit)
- Lazy load heavy libraries (import only when needed)

**Memory Configuration**:
- Start with 256 MB, profile actual usage
- Memory affects CPU allocation (more memory = more CPU)
- Test different memory sizes to find cost-performance sweet spot

**Connection Reuse**:
```python
# Global scope - reuse across invocations
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    # Use clients here
    pass
```

**Async Processing**:
- Textract extraction: Consider Step Functions for long-running tasks
- If extraction takes > 30 seconds consistently, decouple:
  - User uploads → Lambda returns immediately
  - S3 event triggers extraction Lambda
  - Poll status via API or use WebSocket for updates

### DynamoDB Optimization

**Query Patterns**:
- Always query using partition key
- Use sort keys for range queries
- Avoid scans (full table reads)
- Use GSIs for alternate access patterns