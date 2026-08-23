# AWS Serverless Architecture & Implementation

## Project Context

VocabTrainer is a web-based French vocabulary learning application for 9th grade German Gymnasium students. The core feature is extracting vocabulary from scanned workbook images using AI/OCR, then providing typing-based practice sessions. The application must be fully serverless on AWS to minimize operational overhead and costs.

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Browser                          │
│                     (Vue 3 + Tailwind CSS)                      │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ HTTPS
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         CloudFront CDN                          │
│                    (Static Asset Delivery)                      │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├──────────► S3 Bucket (Frontend Static Files)
             │
             │ /api/* requests
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway (REST API)                     │
│                     JWT Authorizer (Cognito)                    │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├──────────► Lambda: upload_handler
             ├──────────► Lambda: extraction_handler
             ├──────────► Lambda: vocab_crud_handler
             ├──────────► Lambda: practice_handler
             └──────────► Lambda: progress_handler
                          │
                          ├──────► DynamoDB Tables
                          ├──────► S3 Bucket (Images)
                          ├──────► AWS Textract
                          └──────► OpenAI Vision API (fallback)
```

### Authentication Flow

```
User → CloudFront → Cognito Hosted UI → Authorization Code
     → Exchange Code for JWT → Store JWT in localStorage
     → All API requests include JWT in Authorization header
     → API Gateway validates JWT via Cognito User Pool
```

## AWS Services Configuration

### 1. Amazon Cognito User Pool

**Purpose:** Authentication and user management with OAuth2 hosted UI

**Configuration:**
- **User Pool Name:** `vocabtrainer-users-prod`
- **Authentication Flow:** OAuth 2.0 Authorization Code Grant
- **Hosted UI:** Enabled with custom domain
- **User Attributes:**
  - email (required, verified)
  - preferred_username (optional)
- **Password Policy:**
  - Minimum length: 8 characters
  - Require uppercase, lowercase, numbers
  - No special characters required (user-friendly for students)
- **App Client:**
  - Name: `vocabtrainer-web-client`
  - Token expiration: 
    - Access token: 1 hour
    - Refresh token: 30 days
  - OAuth flows: Authorization code grant
  - OAuth scopes: openid, email, profile
  - Callback URLs: `https://vocabtrainer.yourdomain.com/callback`, `http://localhost:5173/callback` (development)
  - Sign-out URLs: `https://vocabtrainer.yourdomain.com/`, `http://localhost:5173/`

**Triggers:** None required for MVP

### 2. Amazon S3 Buckets

#### Frontend Bucket

**Bucket Name:** `vocabtrainer-frontend-prod`

**Configuration:**
- Static website hosting: Enabled
- Default document: `index.html`
- Error document: `index.html` (for SPA routing)
- Public access: Blocked (served via CloudFront only)
- Bucket Policy: Allow CloudFront Origin Access Identity

**CORS Configuration:**
```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedOrigins": ["https://vocabtrainer.yourdomain.com"],
    "ExposeHeaders": [],
    "MaxAgeSeconds": 3600
  }
]
```

#### Images Bucket

**Bucket Name:** `vocabtrainer-images-prod`

**Configuration:**
- Versioning: Disabled (workbook images are immutable once uploaded)
- Encryption: Server-side encryption with S3-managed keys (SSE-S3)
- Lifecycle policy:
  - Transition to Glacier after 90 days
  - Delete after 365 days (or user-controlled retention)
- Public access: Blocked (presigned URLs only)

**CORS Configuration:**
```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["PUT", "POST"],
    "AllowedOrigins": ["https://vocabtrainer.yourdomain.com", "http://localhost:5173"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

**Folder Structure:**
```
/{userId}/
  /uploads/
    /{vocabSetId}/
      /original.jpg
      /thumbnail.jpg (optional, generated later)
```

### 3. Amazon DynamoDB Tables

#### Users Table

**Table Name:** `vocabtrainer-users-prod`

**Configuration:**
- Partition Key: `userId` (String) - Cognito sub identifier
- Billing Mode: On-demand (pay per request)
- Point-in-time recovery: Enabled
- Encryption: AWS owned keys

**Attributes:**
```
userId (PK) - String
email - String
displayName - String
createdAt - Number (Unix timestamp)
lastLoginAt - Number (Unix timestamp)
preferences - Map
  └─ defaultDirection - String ("de-fr" or "fr-de")
  └─ sessionLength - Number (default 20)
```

**Global Secondary Indexes:** None required

#### VocabSets Table

**Table Name:** `vocabtrainer-vocabsets-prod`

**Configuration:**
- Partition Key: `vocabSetId` (String) - UUID
- Sort Key: `userId` (String)
- Billing Mode: On-demand
- GSI: `userId-createdAt-index`
  - Partition Key: `userId`
  - Sort Key: `createdAt` (Number, descending)
  - Projection: ALL

**Attributes:**
```
vocabSetId (PK) - String (UUID)
userId (SK) - String
title - String
sourceImageKey - String (S3 key)
extractionStatus - String ("pending" | "processing" | "review" | "approved")
metadata - Map
  └─ chapter - String
  └─ pageNumber - Number
  └─ topic - String
  └─ notes - String
createdAt - Number (Unix timestamp)
updatedAt - Number (Unix timestamp)
itemCount - Number
```

#### VocabItems Table

**Table Name:** `vocabtrainer-vocabitems-prod`

**Configuration:**
- Partition Key: `vocabSetId` (String)
- Sort Key: `itemId` (String) - UUID
- Billing Mode: On-demand

**Attributes:**
```
vocabSetId (PK) - String
itemId (SK) - String (UUID)
german - String
french - String
notes - String (optional)
order - Number (for display ordering)
createdAt - Number
```

#### PracticeSessions Table

**Table Name:** `vocabtrainer-sessions-prod`

**Configuration:**
- Partition Key: `userId` (String)
- Sort Key: `sessionId` (String) - ISO timestamp + random suffix
- Billing Mode: On-demand
- TTL: `expiresAt` attribute (delete after 90 days)

**Attributes:**
```
userId (PK) - String
sessionId (SK) - String
vocabSetId - String
direction - String ("de-fr" | "fr-de")
totalQuestions - Number
correctAnswers - Number
duration - Number (seconds)
detailedResults - List of Maps
  [
    {
      itemId: String,
      question: String,
      correctAnswer: String,
      userAnswer: String,
      correct: Boolean,
      timeSpent: Number
    }
  ]
completedAt - Number (Unix timestamp)
expiresAt - Number (Unix timestamp, for TTL)
```

#### Progress Table

**Table Name:** `vocabtrainer-progress-prod`

**Configuration:**
- Partition Key: `progressKey` (String) - Format: `{userId}#{vocabSetId}`
- Sort Key: `itemId` (String)
- Billing Mode: On-demand

**Attributes:**
```
progressKey (PK) - String
itemId (SK) - String
correctCount - Number
incorrectCount - Number
lastPracticedAt - Number (Unix timestamp)
masteryLevel - Number (0-5, calculated field)
consecutiveCorrect - Number (for spaced repetition future feature)
```

### 4. Amazon API Gateway

**API Name:** `vocabtrainer-api-prod`

**Type:** REST API

**Configuration:**
- Endpoint Type: Regional (CloudFront will handle edge caching)
- Authorization: Cognito User Pool Authorizer
- Binary Media Types: `image/jpeg`, `image/png`, `image/heic`
- CORS: Enabled for all origins during development, restricted in production

**Authorizer Configuration:**
- Name: `CognitoAuthorizer`
- Type: Cognito User Pools
- User Pool: `vocabtrainer-users-prod`
- Token Source: `Authorization` header
- Token Validation: Automatic via Cognito

**Stages:**
- `prod` - Production deployment
- `dev` - Development/testing deployment

**API Resources & Methods:**

```
/vocab
  POST - upload (generate presigned URL)
  GET - list (get all vocab sets for user)
  
  /process
    POST - trigger extraction
  
  /extraction/{vocabSetId}
    GET - get extraction results
  
  /{vocabSetId}
    GET - get specific vocab set details
    PUT - update/approve vocab set
    DELETE - delete vocab set

/practice
  /start
    POST - start practice session
  
  /submit
    POST - submit answer for current question
  
  /complete
    POST - complete session and save results

/progress
  /overview
    GET - get overall user progress
  
  /{vocabSetId}
    GET - get progress for specific vocab set
```

**Request/Response Models:**

```json
// POST /vocab - Upload Request
{
  "fileName": "string",
  "contentType": "string"
}

// Response
{
  "vocabSetId": "uuid",
  "uploadUrl": "presigned-s3-url",
  "expiresIn": 300
}

// POST /vocab/process - Extraction Request
{
  "vocabSetId": "uuid",
  "imageKey": "s3-object-key"
}

// Response
{
  "vocabSetId": "uuid",
  "status": "processing"
}

// GET /vocab/extraction/{vocabSetId} - Extraction Results
{
  "vocabSetId": "uuid",
  "status": "review",
  "items": [
    {
      "itemId": "uuid",
      "german": "das Haus",
      "french": "la maison",
      "confidence": 0.95
    }
  ]
}

// PUT /vocab/{vocabSetId} - Update Vocab Set
{
  "title": "Chapter 3: At Home",
  "metadata": {
    "chapter": "3",
    "pageNumber": 42,
    "topic": "Household"
  },
  "items": [
    {
      "itemId": "uuid",
      "german": "das Haus",
      "french": "la maison"
    }
  ]
}

// POST /practice/start
{
  "vocabSetId": "uuid",
  "direction": "de-fr",
  "questionCount": 20
}

// Response
{
  "sessionId": "string",
  "questions": [
    {
      "questionId": "string",
      "itemId": "uuid",
      "question": "das Haus",
      "questionNumber": 1,
      "totalQuestions": 20
    }
  ]
}

// POST /practice/submit
{
  "sessionId": "string",
  "questionId": "string",
  "answer": "la maison"
}

// Response
{
  "correct": true,
  "correctAnswer": "la maison",
  "nextQuestion": {
    "questionId": "string",
    "itemId": "uuid",
    "question": "die Schule",
    "questionNumber": 2,
    "totalQuestions": 20
  }
}
```

### 5. AWS Lambda Functions

#### General Lambda Configuration

**Runtime:** Python 3.11

**Architecture:** arm64 (Graviton2 for cost savings)

**Memory Allocation:**
- upload_handler: 256 MB
- extraction_handler: 1024 MB (for Textract processing)
- vocab_crud_handler: 512 MB
- practice_handler: 512 MB
- progress_handler: 512 MB

**Timeout:**
- upload_handler: 10 seconds
- extraction_handler: 60 seconds
- vocab_crud_handler: 30 seconds
- practice_handler: 30 seconds
- progress_handler: 30 seconds

**Environment Variables (all functions):**
```
USERS_TABLE=vocabtrainer-users-prod
VOCABSETS_TABLE=vocabtrainer-vocabsets-prod
VOCABITEMS_TABLE=vocabtrainer-vocabitems-prod
SESSIONS_TABLE=vocabtrainer-sessions-prod
PROGRESS_TABLE=vocabtrainer-progress-prod
IMAGES_BUCKET=vocabtrainer-images-prod
OPENAI_API_KEY=<stored-in-secrets-manager>
REGION=us-east-1
```

**IAM Role Permissions (shared execution role):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchGetItem",
        "dynamodb:BatchWriteItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/vocabtrainer-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::vocabtrainer-images-prod/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "textract:AnalyzeDocument",
        "textract:DetectDocumentText"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:vocabtrainer/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

#### Function: upload_handler

**Trigger:** API Gateway POST /vocab

**Purpose:** Generate S3 presigned URL for direct client upload

**Handler:** `upload_handler.lambda_handler`

**Logic:**
1. Extract userId from Cognito JWT claims
2. Generate unique vocabSetId (UUID4)
3. Construct S3 key: `{userId}/uploads/{vocabSetId}/original.jpg`
4. Generate presigned POST URL with 5-minute expiration
5. Create initial record in VocabSets table with status "pending"
6. Return presigned URL and vocabSetId to client

**Dependencies:**
- boto3 (AWS SDK)
- uuid (standard library)

**Error Handling:**
- Invalid userId → 401 Unauthorized
- S3 bucket access error → 500 Internal Server Error
- DynamoDB write failure → 500 Internal Server Error

#### Function: extraction_handler

**Trigger:** API Gateway POST /vocab/process

**Purpose:** Extract vocabulary from uploaded image using AWS Textract

**Handler:** `extraction_handler.lambda_handler`

**Logic:**
1. Validate vocabSetId ownership (userId from JWT matches DynamoDB record)
2. Update VocabSets status to "processing"
3. Call AWS Textract `analyze_document` with TABLES feature
4. Parse Textract response:
   - Identify table structures
   - Extract cells and organize into rows
   - Detect German-French column pairs (heuristics: left=German, right=French)
   - Handle merged cells and annotations
5. If Textract confidence < 0.7 for table detection, fallback to OpenAI Vision API:
   - Send image to GPT-4 Vision
   - Prompt: "Extract vocabulary table from this German school workbook. Return JSON array of {german, french} pairs."
   - Parse JSON response
6. Create VocabItems records in DynamoDB
7. Update VocabSets status to "review", set itemCount
8. Return extracted items with confidence scores

**Dependencies:**
- boto3 (Textract, S3, DynamoDB)
- openai (Python SDK)
- json (standard library)

**Textract API Call:**
```python
response = textract.analyze_document(
    Document={'S3Object': {'Bucket': bucket, 'Name': key}},
    FeatureTypes=['TABLES']
)
```

**OpenAI Fallback Prompt:**
```
You are analyzing a page from a German school workbook for learning French vocabulary.

Extract all vocabulary pairs from any tables or lists on this page. The format is typically:
- Left column: German word/phrase
- Right column: French translation

Return a JSON array with this exact structure:
[
  {"german": "das Haus", "french": "la maison"},
  {"german": "die Schule", "french": "l'école"}
]

Rules:
1. Preserve accents and special characters exactly
2. Ignore headers, page numbers, and instructions
3. Ignore handwritten annotations unless they're clearly vocabulary additions
4. If unclear which column is German vs French, use context (German articles: der/die/das)
5. Return only the JSON array, no additional text
```

**Error Handling:**
- Image not found in S3 → 404 Not Found
- Textract service error → Retry once, then fallback to OpenAI
- OpenAI API error → 500 with error details
- Parsing errors → Return partial results with warning flag

#### Function: vocab_crud_handler

**Trigger:** API Gateway GET/PUT/DELETE /vocab/{vocabSetId}

**Purpose:** CRUD operations on vocabulary sets

**Handler:** `vocab_crud_handler.lambda_handler`

**Operations:**

**GET /vocab (list all):**
1. Query VocabSets GSI `userId-createdAt-index` with userId from JWT
2. Sort by createdAt descending
3. Return array of vocab sets with metadata

**GET /vocab/{vocabSetId}:**
1. Validate ownership
2. Get VocabSets record
3. Query VocabItems by vocabSetId, sort by order
4. Return combined data

**PUT /vocab/{vocabSetId}:**
1. Validate ownership
2. Update VocabSets metadata (title, chapter, etc.)
3. Batch write updated VocabItems
4. Update status to "approved"
5. Recalculate itemCount

**DELETE /vocab/{vocabSetId}:**
1. Validate ownership
2. Delete VocabSets record
3. Query and batch delete all VocabItems
4. Delete associated image from S3
5. Delete associated progress records

**Dependencies:**
- boto3 (DynamoDB, S3)

**Error Handling:**
- Unauthorized access → 403 Forbidden
- Resource not found → 404 Not Found
- Validation errors → 400 Bad Request

#### Function: practice_handler

**Trigger:** API Gateway POST /practice/start, /practice/submit, /practice/complete

**Purpose:** Manage practice sessions and answer validation

**Handler:** `practice_handler.lambda_handler`

**Operations:**

**POST /practice/start:**
1. Validate vocabSetId ownership
2. Query VocabItems for the set
3. Shuffle items
4. Limit to requested questionCount (default 20)
5. Create session record in DynamoDB with status "active"
6. Return first question

**POST /practice/submit:**
1. Validate sessionId ownership
2. Retrieve correct answer from VocabItems
3. Normalize both answers (lowercase, strip accents for comparison)
4. Check correctness with fuzzy matching (Levenshtein distance ≤ 2)
5. Update session's detailedResults array
6. Update Progress table (increment correct/incorrect counts)
7. Return feedback and next question

**POST /practice/complete:**
1. Validate sessionId ownership
2. Calculate final score
3. Update session record with completedAt timestamp
4. Update Progress masteryLevel for each item (algorithm: `min(5, correctCount / (correctCount + incorrectCount) * 5)`)
5. Return session summary with statistics

**Answer Normalization Logic:**
```python
def normalize(text):
    # Remove leading/trailing whitespace
    text = text.strip().lower()
    # Remove accents for fuzzy matching
    import unicodedata
    text = ''.join(c for c in unicodedata.normalize('NFD', text) 
                   if unicodedata.category(c) != 'Mn')
    # Remove common punctuation
    text = text.replace('.', '').replace(',', '').replace('!', '').replace('?', '')
    return text

def is_correct(user_answer, correct_answer):
    norm_user = normalize(user_answer)
    norm_correct = normalize(correct_answer)
    
    # Exact match
    if norm_user == norm_correct:
        return True
    
    # Fuzzy match (Levenshtein distance ≤ 2)
    from Levenshtein import distance
    if distance(norm_user, norm_correct) <= 2:
        return True
    
    return False
```

**Dependencies:**
- boto3 (DynamoDB)
- python-Levenshtein (fuzzy matching)
- uuid, random (standard library)

**Error Handling:**
- Invalid session → 404 Not Found
- Session already completed → 400 Bad Request
- Missing required fields → 400 Bad Request

#### Function: progress_handler

**Trigger:** API Gateway GET /progress/overview, /progress/{vocabSetId}

**Purpose:** Calculate and return progress statistics

**Handler:** `progress_handler.lambda_handler`

**Operations:**

**GET /progress/overview:**
1. Query all VocabSets for user
2. For each set, aggregate Progress records
3. Calculate:
   - Total words across all sets
   - Total practiced words (progress records exist)
   - Average mastery level
   - Total practice sessions (query Sessions table)
   - Total time spent
4. Return summary object

**GET /progress/{vocabSetId}:**
1. Validate ownership
2. Query Progress records for vocabSetId
3. Join with VocabItems to get word details
4. Calculate per-word statistics:
   - Accuracy percentage
   - Times practiced
   - Last practiced date
   - Mastery level
5. Return detailed progress array

**Response Format:**
```json
// Overview
{
  "totalVocabSets": 5,
  "totalWords": 247,
  "practicedWords": 183,
  "averageMastery": 3.2,
  "totalSessions": 42,
  "totalTimeMinutes": 380,
  "recentSessions": [
    {
      "sessionId": "...",
      "vocabSetTitle": "Chapter 3",
      "score": "18/20",
      "completedAt": 1703012345
    }
  ]
}

// Vocab Set Detail
{
  "vocabSetId": "...",
  "title": "Chapter 3",
  "progress": [
    {
      "itemId": "...",
      "german": "das Haus",
      "french": "la maison",
      "correctCount": 12,
      "incorrectCount": 3,
      "accuracy": 0.8,
      "masteryLevel": 4,
      "lastPracticedAt": 1703012345
    }
  ],
  "overallAccuracy": 0.82,
  "masteredCount": 15,
  "inProgressCount": 8,
  "notPracticedCount": 2
}
```

**Dependencies:**
- boto3 (DynamoDB)

**Error Handling:**
- Invalid vocabSetId → 404 Not Found
- No progress data → Return empty progress with metadata

### 6. Amazon CloudFront

**Distribution Name:** `vocabtrainer-cdn-prod`

**Origin Configuration:**
- Origin 1: S3 bucket `vocabtrainer-frontend-prod`
  - Origin Access Identity: Create new OAI
  - Protocol: HTTPS only
- Origin 2: API Gateway `vocabtrainer-api-prod`
  - Custom origin, HTTPS only
  - Origin path: `/prod`

**Behavior Configuration:**
- Default behavior: Origin 1 (frontend)
  - Viewer protocol: Redirect HTTP to HTTPS
  - Allowed HTTP methods: GET, HEAD, OPTIONS
  - Cache policy: CachingOptimized
  - Compress objects: Yes
- Path pattern `/api/*`: Origin 2 (API Gateway)
  - Viewer protocol: HTTPS only
  - Allowed HTTP methods: GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE
  - Cache policy: CachingDisabled (all requests hit API)
  - Origin request policy: Include all query strings, headers, cookies

**Custom Error Responses:**
- 403 Forbidden → Return /index.html (HTTP 200) for SPA routing
- 404 Not Found → Return /index.html (HTTP 200) for SPA routing

**SSL Certificate:**
- ACM certificate for `vocabtrainer.yourdomain.com`
- Must be in us-east-1 region for CloudFront

**Security Headers (via Lambda@Edge or CloudFront Functions):**
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'
```

### 7. AWS Textract

**Usage:** Document analysis for vocabulary extraction

**API Call:** `analyze_document` with `FeatureTypes=['TABLES']`

**Input:** S3 object reference (bucket + key)

**Output:** JSON structure containing:
- Blocks (WORD, LINE, TABLE, CELL types)
- Relationships between blocks
- Confidence scores

**Cost Optimization:**
- Only process pages with tables (pre-check with `detect_document_text` first, cheaper)
- Cache results in DynamoDB to avoid reprocessing
- Set max document size limit (5 MB) to prevent abuse

**Fallback Strategy:**
If Textract fails or confidence < 70%:
1. Log failure reason
2. Call OpenAI Vision API with the same image
3. Use structured prompt for JSON output
4. Flag extraction as "AI-assisted" in metadata

### 8. CloudWatch Logging & Monitoring

**Log Groups:**
- `/aws/lambda/vocabtrainer-upload-handler-prod`
- `/aws/lambda/vocabtrainer-extraction-handler-prod`
- `/aws/lambda/vocabtrainer-vocab-crud-handler-prod`
- `/aws/lambda/vocabtrainer-practice-handler-prod`
- `/aws/lambda/vocabtrainer-progress-handler-prod`
- `/aws/apigateway/vocabtrainer-api-prod`

**Retention:** 7 days (reduce costs, extend to 30 days for production)

**Alarms:**
- Lambda errors > 5 in 5 minutes
- API Gateway 5xx errors > 10 in 5 minutes
- Textract throttling errors
- DynamoDB throttling (should not occur with on-demand)
- Lambda duration > 80% of timeout

**Metrics to Track:**
- API latency (p50, p95, p99)
- Lambda invocation count
- DynamoDB read/write capacity units
- S3 request count
- Textract API call count (cost monitoring)
- OpenAI API call count (cost monitoring)

**Dashboard Widgets:**
- API request rate over time
- Lambda error rate
- Extraction success rate (Textract vs OpenAI fallback ratio)
- User registration trend
- Active practice sessions

## Infrastructure as Code

### Recommended Approach: AWS SAM (Serverless Application Model)

**Project Structure:**
```
vocabtrainer-backend/
├── template.yaml (SAM template)
├── samconfig.toml (deployment config)
├── functions/
│   ├── upload_handler/
│   │   ├── app.py
│   │   └── requirements.txt
│   ├── extraction_handler/
│   │   ├── app.py
│   │   └── requirements.txt
│   ├── vocab_crud_handler/
│   │   ├── app.py
│   │   └── requirements.txt
│   ├── practice_handler/
│   │   ├── app.py
│   │   └── requirements.txt
│   └── progress_handler/
│       ├── app.py
│       └── requirements.txt
└── layers/
    └── common/
        └── python/
            └── utils.py (shared utilities)
```

**SAM Template Highlights:**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Runtime: python3.11
    Architecture: arm64
    Timeout: 30
    MemorySize: 512
    Environment:
      Variables:
        USERS_TABLE: !Ref UsersTable
        VOCABSETS_TABLE: !Ref VocabSetsTable
        VOCABITEMS_TABLE: !Ref VocabItemsTable
        SESSIONS_TABLE: !Ref SessionsTable
        PROGRESS_TABLE: !Ref ProgressTable
        IMAGES_BUCKET: !Ref ImagesBucket
        REGION: !Ref AWS::Region

Parameters:
  Environment:
    Type: String
    Default: prod
    AllowedValues:
      - dev
      - prod
  OpenAIApiKeySecretArn:
    Type: String
    Description: ARN of the Secrets Manager secret containing OpenAI API key

Resources:
  # Cognito User Pool
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub vocabtrainer-users-${Environment}
      AutoVerifiedAttributes:
        - email
      Schema:
        - Name: email
          Required: true
          Mutable: false
      Policies:
        PasswordPolicy:
          MinimumLength: 8
          RequireUppercase: true
          RequireLowercase: true
          RequireNumbers: true
          RequireSymbols: false

  UserPoolClient:
    Type: AWS::Cognito::UserPoolClient
    Properties:
      ClientName: !Sub vocabtrainer-web-client-${Environment}
      UserPoolId: !Ref UserPool
      GenerateSecret: false
      AllowedOAuthFlows:
        - code
      AllowedOAuthScopes:
        - openid
        - email
        - profile
      CallbackURLs:
        - !If [IsProd, 'https://vocabtrainer.yourdomain.com/callback', 'http://localhost:5173/callback']
      LogoutURLs:
        - !If [IsProd, 'https://vocabtrainer.yourdomain.com/', 'http://localhost:5173/']
      SupportedIdentityProviders:
        - COGNITO

  UserPoolDomain:
    Type: AWS::Cognito::UserPoolDomain
    Properties