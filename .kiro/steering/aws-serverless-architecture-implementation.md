# AWS Serverless Architecture & Implementation

## Project Context

VocabTrainer is a web-based vocabulary learning application for German Gymnasium students. The core feature is extracting vocabulary from scanned workbook pages using AI/OCR (Textract + Bedrock), then providing typing-based practice sessions with smart repetition and error pattern analysis. The application supports multiple target languages (French, Spanish, etc.) and includes a league system for class-based competition managed by teachers.

The entire infrastructure runs on AWS using serverless architecture.

- **Region:** eu-central-1
- **Account:** 730335610692
- **Stack naming:** vocabtrainer-{stage} (e.g. vocabtrainer-dev, vocabtrainer-prod)

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
│                     Cognito User Pool Authorizer                │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├──────────► Lambda: upload_handler
             ├──────────► Lambda: extraction_handler
             ├──────────► Lambda: vocab_crud_handler
             ├──────────► Lambda: practice_handler
             ├──────────► Lambda: progress_handler
             └──────────► Lambda: league_handler
                          │
                          ├──────► DynamoDB (7 tables)
                          ├──────► S3 Bucket (Images)
                          ├──────► AWS Textract (OCR)
                          └──────► Amazon Bedrock (LLM extraction)
```

### Design Principles

1. **Serverless First**: Use managed services to minimize operational overhead
2. **Pay-per-use**: No fixed costs, scale to zero when not in use
3. **Security by Default**: Least privilege IAM roles, encrypted storage
4. **Stateless Functions**: Each Lambda invocation is independent
5. **Multi-language**: VocabSets use source/target fields with a targetLanguage attribute
6. **DynamoDB Decimal handling**: Always use `default=str` in `json.dumps` calls

### Authentication Flow

```
User → CloudFront → Cognito Hosted UI → Authorization Code
     → Exchange Code for JWT → Store JWT in localStorage
     → All API requests include JWT in Authorization header
     → API Gateway validates JWT via Cognito User Pool Authorizer
     → Lambda reads userId from 'sub' claim, groups from 'cognito:groups' claim
```

## AWS Services Configuration

### 1. Amazon Cognito User Pool

**Purpose:** Authentication, user management, and role-based access (teachers group)

**Configuration:**
- **User Pool Name:** `vocabtrainer-users-{stage}`
- **Authentication Flow:** OAuth 2.0 Authorization Code Grant
- **Hosted UI:** Enabled
- **Username Attributes:** email
- **User Attributes:**
  - email (required, verified)
- **Password Policy:**
  - Minimum length: 8 characters
  - Require uppercase, lowercase, numbers
  - No special characters required (student-friendly)
- **Account Recovery:** verified_email
- **App Client:**
  - Name: `vocabtrainer-web-client-{stage}`
  - Generate secret: No (public web client)
  - Explicit auth flows: ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH, ALLOW_USER_SRP_AUTH
  - OAuth flows: Authorization code grant
  - OAuth scopes: openid, email, profile
  - Callback URLs: `http://localhost:5173/callback`, `https://{CloudFront}/callback`
  - Sign-out URLs: `http://localhost:5173`, `https://{CloudFront}`
- **Token Expiration:**
  - Access token: 1 hour
  - Refresh token: 30 days

**Groups:**
- **teachers**: Cognito group for teacher accounts. Backend reads `cognito:groups` claim from the JWT to check membership. Teachers can create/manage leagues and are filtered from leaderboards.

**Domain:**
- `vocabtrainer-{stage}-{accountId}.auth.{region}.amazoncognito.com`

### 2. Amazon S3 Buckets

#### Frontend Bucket

**Bucket Name:** `vocabtrainer-frontend-{stage}-{accountId}`

**Configuration:**
- Static website hosting: via CloudFront (not S3 website endpoint)
- Public access: Blocked (served via CloudFront OAC only)
- Bucket Policy: Allow CloudFront service principal

#### Images Bucket

**Bucket Name:** `vocabtrainer-images-{stage}-{accountId}`

**Configuration:**
- Public access: Blocked (presigned URLs only)
- Encryption: SSE-S3 (AES-256)
- Versioning: Disabled
- Lifecycle policy: Delete after 90 days
- CORS: Allow PUT/POST/GET from all origins

**Folder Structure:**
```
/images/{userId}/{vocabSetId}/{timestamp}-original.{ext}
```

### 3. Amazon DynamoDB Tables (7 tables)

All tables use on-demand billing (PAY_PER_REQUEST) and are named `vocabtrainer-{tablename}-{stage}`.

#### Table 1: Users

**Table Name:** `vocabtrainer-users-{stage}`

```
userId (PK) - String (Cognito sub)

Attributes:
  - email: String
  - displayName: String
  - role: String ("student" | "teacher")
  - leagueId: String (quick lookup for current league membership)
  - createdAt: Number (Unix timestamp)
  - lastLoginAt: Number
  - preferences: Map
    └─ defaultDirection: String
    └─ sessionLength: Number (default 20)
```

#### Table 2: VocabSets

**Table Name:** `vocabtrainer-vocabsets-{stage}`

```
vocabSetId (PK) - String (UUID)
userId (SK) - String

Attributes:
  - title: String
  - sourceImageKey: String (S3 key, first image)
  - imageKeys: List<String> (all image S3 keys for multi-page sets)
  - targetLanguage: String (e.g. "fr", "es", "en")
  - extractionStatus: String ("pending" | "processing" | "review" | "approved" | "failed")
  - extractionMethod: String ("textract" | "bedrock_from_text")
  - metadata: Map
    └─ chapter: String
    └─ pageNumber: Number
    └─ topic: String
    └─ notes: String
    └─ tags: List<String>
  - createdAt: Number
  - updatedAt: Number
  - itemCount: Number

GSI: userId-createdAt-index
  Partition Key: userId
  Sort Key: createdAt (Number)
  Projection: ALL
```

#### Table 3: VocabItems

**Table Name:** `vocabtrainer-vocabitems-{stage}`

```
vocabSetId (PK) - String
itemId (SK) - String (UUID)

Attributes:
  - source: String (German word/phrase)
  - target: String (target language word/phrase)
  - notes: String (optional)
  - order: Number (display ordering)
  - confidence: Number (0-100, extraction confidence)
  - imageKey: String (S3 key of the source image for this item)
  - createdAt: Number
  - updatedAt: Number
  - isActive: Boolean (soft delete)
```

**Note:** Fields are `source` and `target`, not `german` and `french`. The target language is determined by the parent VocabSet's `targetLanguage` field.

#### Table 4: PracticeSessions

**Table Name:** `vocabtrainer-sessions-{stage}`

```
userId (PK) - String
sessionId (SK) - String (UUID)

Attributes:
  - vocabSetId: String
  - direction: String ("de-fr" | "fr-de" | "source-target" | "target-source")
  - totalQuestions: Number
  - correctAnswers: Number
  - score: Number (percentage)
  - duration: Number (seconds)
  - status: String ("active" | "completed")
  - startedAt: Number
  - completedAt: Number
  - questions: List<Map> (full question data with answers)
  - detailedResults: List<Map>
    [
      {
        questionId: String,
        itemId: String,
        question: String,
        correctAnswer: String,
        userAnswer: String,
        correct: Boolean,
        answeredAt: Number
      }
    ]
  - expiresAt: Number (TTL, 90 days after creation)

GSI: vocabSetId-completedAt-index
  Partition Key: vocabSetId
  Sort Key: completedAt (Number)
  Projection: ALL

TTL: expiresAt
```

#### Table 5: Progress

**Table Name:** `vocabtrainer-progress-{stage}`

```
progressKey (PK) - String (format: "{userId}#{vocabSetId}")
itemId (SK) - String

Attributes:
  - userId: String
  - vocabSetId: String
  - correctCount: Number
  - incorrectCount: Number
  - lastPracticedAt: Number
  - masteryLevel: Number (0-5, calculated)
  - consecutiveCorrect: Number
  - recentErrors: List<Map> (last 5 wrong answers for error pattern detection)
    [
      {
        answer: String,
        timestamp: Number
      }
    ]
```

**recentErrors:** Trimmed to the last 5 entries. Used by `_analyze_error_patterns` in the practice handler to detect article/gender errors and repeated mistakes on the same words.

#### Table 6: Leagues

**Table Name:** `vocabtrainer-leagues-{stage}`

```
leagueId (PK) - String (UUID)

Attributes:
  - name: String (e.g. "Klasse 9b Französisch")
  - teacherUserId: String (Cognito sub of the creating teacher)
  - joinCode: String (6-char alphanumeric, e.g. "ABC123")
  - scoreMode: String ("total" | "weekly" | "accuracy" | "combined")
  - vocabSetIds: List<String> (assigned vocab sets)
  - createdAt: Number
  - updatedAt: Number

GSI: joinCode-index
  Partition Key: joinCode
  Projection: ALL
```

#### Table 7: LeagueMembers

**Table Name:** `vocabtrainer-league-members-{stage}`

```
leagueId (PK) - String
userId (SK) - String

Attributes:
  - displayName: String
  - role: String ("student")
  - currentStreak: Number
  - totalCorrect: Number
  - totalAttempts: Number
  - weeklyCorrect: Number
  - weekStartDate: String (ISO date)
  - lastPracticeDate: String
  - joinedAt: Number
```

**Note:** The teacher is NOT a member of LeagueMembers. The teacher is identified via `Leagues.teacherUserId` and is filtered from leaderboard results.

### 4. Amazon API Gateway

**API Name:** `vocabtrainer-api-{stage}`

**Type:** REST API

**Configuration:**
- Endpoint Type: Regional
- Authorization: Cognito User Pool Authorizer (default for all endpoints)
- CORS: Allow GET, POST, PUT, DELETE, OPTIONS; Content-Type + Authorization headers; all origins

**API Resources & Methods:**

```
POST   /vocab/upload                          → upload_handler
POST   /vocab/process                         → extraction_handler
GET    /vocab/extraction/{vocabSetId}         → extraction_handler
GET    /vocab                                 → vocab_crud_handler
GET    /vocab/{vocabSetId}                    → vocab_crud_handler
PUT    /vocab/{vocabSetId}                    → vocab_crud_handler
DELETE /vocab/{vocabSetId}                    → vocab_crud_handler

POST   /practice/start                        → practice_handler
POST   /practice/submit                       → practice_handler
POST   /practice/complete                     → practice_handler

GET    /progress/overview                     → progress_handler
GET    /progress/{vocabSetId}                 → progress_handler

POST   /league                                → league_handler (create)
POST   /league/join                           → league_handler (join)
GET    /league/{leagueId}                     → league_handler (get)
PUT    /league/{leagueId}                     → league_handler (update)
DELETE /league/{leagueId}                     → league_handler (delete)
GET    /league/{leagueId}/leaderboard         → league_handler
GET    /league/{leagueId}/members             → league_handler
DELETE /league/{leagueId}/members/{memberId}  → league_handler (remove)
PUT    /users/profile                         → league_handler (update displayName)

POST   /invite                                → invite_handler (create)
GET    /invite/{token}                        → invite_handler (validate, no auth)
```

### 5. AWS Lambda Functions (7 functions + SharedLayer)

#### General Configuration

**Runtime:** Python 3.11
**Architecture:** arm64 (Graviton2)
**Default Memory:** 512 MB
**Default Timeout:** 30 seconds

**Environment Variables (all functions via Globals):**
```
ENVIRONMENT={stage}
USERS_TABLE=vocabtrainer-users-{stage}
VOCABSETS_TABLE=vocabtrainer-vocabsets-{stage}
VOCABITEMS_TABLE=vocabtrainer-vocabitems-{stage}
SESSIONS_TABLE=vocabtrainer-sessions-{stage}
PROGRESS_TABLE=vocabtrainer-progress-{stage}
IMAGES_BUCKET=vocabtrainer-images-{stage}-{accountId}
LEAGUES_TABLE=vocabtrainer-leagues-{stage}
LEAGUE_MEMBERS_TABLE=vocabtrainer-league-members-{stage}
REGION={AWS::Region}
```

**SharedLayer:**
- Layer Name: `vocabtrainer-shared-{stage}`
- Contains shared Python modules under `python/lib/`:
  - `utils.py` — build_response, build_error_response, get_user_id_from_event, generate_uuid, get_timestamp, parse_body, get_path_parameter
  - `validation.py` — validate_uuid, validate_file_upload, validate_practice_options
  - `languages.py` — get_language, DEFAULT_TARGET_LANGUAGE, language config (name, nameEnglish per code)
  - `auth.py` — auth utilities
- Compatible with python3.11 and arm64

#### Function 1: upload_handler

**Function Name:** `vocabtrainer-upload-handler-{stage}`
**Trigger:** POST /vocab/upload

**Purpose:** Generate S3 presigned PUT URL for direct client upload and create/update VocabSet record.

**Logic:**
1. Extract userId from Cognito JWT claims
2. If `vocabSetId` provided in body, verify ownership and append image; otherwise generate new vocabSetId
3. Construct S3 key: `images/{userId}/{vocabSetId}/{timestamp}-original.{ext}`
4. Generate presigned PUT URL (5-minute expiration)
5. Create initial VocabSet record with `imageKeys` list and status "pending", or append to existing `imageKeys`
6. Return presigned URL, vocabSetId, imageKey

**IAM Permissions:**
- S3: PutObject, GetObject, DeleteObject on images bucket
- DynamoDB: CRUD on VocabSets table

#### Function 2: extraction_handler

**Function Name:** `vocabtrainer-extraction-handler-{stage}`
**Memory:** 1024 MB
**Timeout:** 300 seconds (5 minutes)
**Trigger:** POST /vocab/process, GET /vocab/extraction/{vocabSetId}

**Purpose:** Two-stage vocabulary extraction pipeline: Textract OCR → Bedrock LLM extraction.

**Extraction Pipeline:**

1. **Stage 1 — Textract OCR:**
   - Call `textract.analyze_document` with `FeatureTypes=['TABLES']`
   - Parse response via `TextractParser` class to extract table-based vocabulary pairs and raw OCR text (all LINE blocks)
   - Returns `(vocab_pairs, confidence, raw_text)`

2. **Stage 2 — Bedrock LLM Extraction:**
   - Always prefer Bedrock extraction from raw text when raw text has >50 chars
   - Call `extract_with_bedrock_from_text(raw_text, target_language)` using Amazon Nova Pro (`eu.amazon.nova-pro-v1:0`) via the Converse API
   - The LLM prompt instructs extraction of source/target vocabulary pairs from the raw OCR text, handling free-text layouts, lautschrift, OCR artifacts, etc.
   - If Bedrock returns >= as many pairs as Textract table parsing, use Bedrock results (extraction_method = "bedrock_from_text")
   - If extraction came from Textract table parsing, additionally verify/clean with `verify_with_bedrock()`

3. **Store results:** Batch write VocabItems to DynamoDB. Update VocabSet status and itemCount (ADD for multi-page support).

**Bedrock Configuration:**
```python
bedrock_client.converse(
    modelId='eu.amazon.nova-pro-v1:0',
    messages=[{'role': 'user', 'content': [{'text': prompt}]}],
    inferenceConfig={'maxTokens': 4096}
)
```

**IAM Permissions:**
- S3: GetObject on images bucket
- DynamoDB: CRUD on VocabSets, VocabItems
- Textract: AnalyzeDocument, DetectDocumentText
- Bedrock: InvokeModel on foundation-model/* and inference-profile/*

**Note:** The OpenAI fallback code still exists in the codebase for legacy reasons but is not the primary path. Bedrock is the production extraction method.

#### Function 3: vocab_crud_handler

**Function Name:** `vocabtrainer-vocab-crud-handler-{stage}`
**Trigger:** GET/PUT/DELETE /vocab, /vocab/{vocabSetId}

**Purpose:** CRUD operations on vocabulary sets and items.

**Operations:**
- **GET /vocab:** Query GSI userId-createdAt-index, return all sets sorted by date
- **GET /vocab/{vocabSetId}:** Get set metadata + query all VocabItems
- **PUT /vocab/{vocabSetId}:** Update metadata, batch write updated items, update status
- **DELETE /vocab/{vocabSetId}:** Delete VocabSet + all VocabItems + S3 images + progress records

**IAM Permissions:**
- DynamoDB: CRUD on VocabSets, VocabItems; Read on Progress
- S3: CRUD on images bucket

#### Function 4: practice_handler

**Function Name:** `vocabtrainer-practice-handler-{stage}`
**Trigger:** POST /practice/start, /practice/submit, /practice/complete

**Purpose:** Manage practice sessions with smart repetition, answer validation, error pattern tracking, and league stat updates.

**Key Features:**

**Smart Repetition (`_prioritize_items`):**
- On session start, fetches progress data for all items in the vocab set
- Calculates priority score per item based on:
  - Low mastery level → higher priority
  - Recent errors (from `recentErrors` list) → boost by 1.5 per error (max 3)
  - High error rate → boost by up to 2.0
  - Never practiced → medium priority (5.0)
  - High consecutive correct → penalty (-0.5 per streak, max 3)
- Adds random factor (0–1.5) to avoid identical ordering
- Sorts descending by priority: weakest words appear first

**Error Pattern Tracking (`_update_item_progress`):**
- On incorrect answer: appends `{answer, timestamp}` to `recentErrors` in Progress table
- Trims `recentErrors` to last 5 entries
- On correct answer: resets `consecutiveCorrect` counter is incremented (on error it resets to 0)
- Recalculates `masteryLevel = min(5, int((correct / total) * 5))`

**Error Pattern Analysis (`_analyze_error_patterns`):**
- Called after session completion for wrong answers
- Detects **article errors**: same word body but different article (e.g. "le maison" vs "la maison")
- Detects **repeated mistakes**: items where `recentErrors` has ≥ 2 entries
- Returns German-language summary text for the student

**League Stats Update (`_update_league_stats`):**
- After session completion, checks if user is in a league
- Updates LeagueMembers stats: totalCorrect, totalAttempts, weeklyCorrect, currentStreak, lastPracticeDate

**Answer Checking:**
- Uses `answer_checker.py` module with fuzzy matching
- Normalize: lowercase, trim, strip accents, remove punctuation
- Levenshtein distance ≤ 2 for minor typos

**IAM Permissions:**
- DynamoDB: CRUD on VocabItems, PracticeSessions, Progress, LeagueMembers; Read on Users

#### Function 5: progress_handler

**Function Name:** `vocabtrainer-progress-handler-{stage}`
**Trigger:** GET /progress/overview, GET /progress/{vocabSetId}

**Purpose:** Calculate and return progress statistics.

**Operations:**

**GET /progress/overview:**
- Query all VocabSets for user
- Aggregate Progress records across all sets
- Calculate: total words, practiced words, average mastery, total sessions, total time
- Return recent sessions list

**GET /progress/{vocabSetId}:**
- Query Progress records by compositeKey (userId#vocabSetId)
- Join with VocabItems for word details
- Calculate per-word statistics: accuracy, mastery level, times practiced
- Identify mastered vs in-progress vs not-practiced counts

**IAM Permissions:**
- DynamoDB: Read on Progress, PracticeSessions, VocabSets, VocabItems

#### Function 6: league_handler

**Function Name:** `vocabtrainer-league-handler-{stage}`
**Trigger:** Multiple league and profile routes (see API Gateway section)

**Purpose:** Manage leagues (Liga) — CRUD, join, leaderboard, members, remove, profile update.

**Operations:**

- **POST /league** — Teacher creates a league. Requires `cognito:groups` containing "teachers". Generates 6-char join code.
- **POST /league/join** — Student joins a league by join code. Checks user not already in a league. Creates LeagueMembers record.
- **GET /league/{leagueId}** — Get league details + caller's member stats. Requires membership or teacher.
- **PUT /league/{leagueId}** — Teacher updates league (name, scoreMode, vocabSetIds). Teacher-only.
- **DELETE /league/{leagueId}** — Teacher deletes league. Clears leagueId from all member Users. Batch deletes all LeagueMembers. Teacher-only.
- **GET /league/{leagueId}/leaderboard** — Get ranked leaderboard. Teacher filtered out by `teacherUserId`. Scores calculated by `scoreMode` (total, weekly, accuracy, combined). Weekly stats auto-reset on new week (Berlin timezone).
- **GET /league/{leagueId}/members** — Teacher gets all members with stats. Teacher-only.
- **DELETE /league/{leagueId}/members/{memberId}** — Teacher removes a member. Clears leagueId from user. Teacher-only.
- **PUT /users/profile** — Update user's displayName (also propagates to LeagueMembers).

**Teacher Detection:**
```python
def _is_teacher(event):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
    groups = claims.get('cognito:groups', '')
    if isinstance(groups, str):
        return 'teachers' in [g.strip() for g in groups.split(',')]
    return False
```

**IAM Permissions:**
- DynamoDB: CRUD on Leagues, LeagueMembers, Users; Read on VocabSets, Progress, PracticeSessions

#### Function 7: invite_handler

**Function Name:** `vocabtrainer-invite-handler-{stage}`
**Trigger:** POST /invite, GET /invite/{token} (GET has no auth)

**Purpose:** Create and validate invite tokens for controlled signup.

### 6. Amazon Bedrock

**Purpose:** Vocabulary extraction from raw OCR text (primary extraction method) and verification/cleaning of Textract table-parsed results.

**Model:** Amazon Nova Pro (`eu.amazon.nova-pro-v1:0`)

**API:** Converse API (`bedrock-runtime.converse`)

**Usage in extraction pipeline:**
1. `extract_with_bedrock_from_text()` — Takes raw OCR text from Textract, sends to Nova Pro with a detailed German-language prompt to extract source/target vocabulary pairs. Handles free-text layouts, lautschrift, OCR artifacts, compound translations.
2. `verify_with_bedrock()` — Takes Textract table-parsed pairs and cleans them: removes non-vocabulary entries (headers, instructions), formats multiple meanings with semicolons, corrects OCR errors.

**IAM Permission:**
```yaml
- Effect: Allow
  Action:
    - bedrock:InvokeModel
  Resource:
    - 'arn:aws:bedrock:*::foundation-model/*'
    - !Sub 'arn:aws:bedrock:*:${AWS::AccountId}:inference-profile/*'
```

### 7. AWS Textract

**Purpose:** OCR — extract raw text and table structures from workbook images.

**API:** `analyze_document` with `FeatureTypes=['TABLES']`

**Input:** S3 object reference (bucket + key)

**Output used:**
- LINE blocks → concatenated into raw text for Bedrock extraction
- TABLE/CELL blocks → parsed by `TextractParser` for table-based vocabulary pairs with confidence scores

**Role in pipeline:** Textract is the OCR stage only. The LLM (Bedrock) handles the intelligent extraction of vocabulary pairs from the raw text. This two-stage approach handles free-text layouts that don't use strict table structures.

### 8. Amazon CloudFront

**Distribution for frontend SPA.**

**Origin:** S3 bucket via Origin Access Control (OAC), not OAI.

**Configuration:**
- Default root object: `index.html`
- Viewer protocol: Redirect HTTP to HTTPS
- Compress: Yes
- Price class: PriceClass_100 (US, Canada, Europe)
- Custom error responses: 403 → /index.html (200), 404 → /index.html (200) — for SPA routing

### 9. CloudWatch Logging & Monitoring

**Log Groups:**
- `/aws/lambda/vocabtrainer-upload-handler-{stage}`
- `/aws/lambda/vocabtrainer-extraction-handler-{stage}`
- `/aws/lambda/vocabtrainer-vocab-crud-handler-{stage}`
- `/aws/lambda/vocabtrainer-practice-handler-{stage}`
- `/aws/lambda/vocabtrainer-progress-handler-{stage}`
- `/aws/lambda/vocabtrainer-league-handler-{stage}`
- `/aws/lambda/vocabtrainer-invite-handler-{stage}`

**Retention:** 7 days (dev), 30 days (prod)

**Structured Logging:** All handlers use Python `logging` with `json.dumps` for structured log events. Always use `default=str` for DynamoDB Decimal serialization.

**Key Metrics:**
- API latency (p50, p95, p99)
- Lambda invocation count and error rate
- DynamoDB consumed capacity
- Textract and Bedrock API call counts (cost monitoring)
- Extraction success rate (textract vs bedrock_from_text)

**Alarms:**
- Lambda errors > 5 in 5 minutes
- API Gateway 5xx errors > 10 in 5 minutes
- Textract/Bedrock throttling
- Lambda duration > 80% of timeout

## Infrastructure as Code

### AWS SAM Template

**Location:** `backend/template.yaml`

**Project Structure:**
```
backend/
├── template.yaml
├── samconfig.toml
├── functions/
│   ├── upload_handler/
│   │   ├── app.py
│   │   └── requirements.txt
│   ├── extraction_handler/
│   │   ├── app.py
│   │   ├── textract_parser.py
│   │   └── requirements.txt
│   ├── vocab_crud_handler/
│   │   ├── app.py
│   │   └── requirements.txt
│   ├── practice_handler/
│   │   ├── app.py
│   │   ├── answer_checker.py
│   │   └── requirements.txt
│   ├── progress_handler/
│   │   ├── app.py
│   │   └── requirements.txt
│   ├── league_handler/
│   │   ├── app.py
│   │   └── requirements.txt
│   └── invite_handler/
│       ├── app.py
│       └── requirements.txt
├── layers/
│   └── shared/
│       └── python/
│           └── lib/
│               ├── __init__.py
│               ├── utils.py
│               ├── validation.py
│               ├── languages.py
│               └── auth.py
└── tests/
```

**Deployment:**
```bash
cd backend
sam build
sam deploy --config-env default   # dev
sam deploy --config-env prod      # prod
```

**samconfig.toml:**
- Default region: eu-central-1
- Dev stack: vocabtrainer-dev
- Prod stack: vocabtrainer-prod
- Capabilities: CAPABILITY_IAM CAPABILITY_AUTO_EXPAND

## Security Implementation

### IAM Roles and Policies

Each Lambda function has its own execution role with minimal permissions via SAM policy templates:
- `S3CrudPolicy` / `S3ReadPolicy` for images bucket
- `DynamoDBCrudPolicy` / `DynamoDBReadPolicy` per table
- Explicit statements for Textract and Bedrock

### Encryption

- **At rest:** DynamoDB encrypted with AWS managed keys; S3 with SSE-S3
- **In transit:** HTTPS only (CloudFront + API Gateway); TLS 1.2 minimum

### Input Validation

- Shared `validation.py` module validates UUIDs, file uploads (type, size), practice options
- Each handler validates ownership (userId from JWT matches DynamoDB record)
- File upload: JPG, PNG, HEIC only; max 10 MB

### DynamoDB Decimal Handling

DynamoDB returns numbers as `Decimal` type in Python. Always use `json.dumps(data, default=str)` to serialize responses. This is enforced across all handlers.

## Performance Optimization

### Lambda

- arm64 architecture for faster cold starts and better price/performance
- Global-scope AWS client initialization for connection reuse across invocations
- SharedLayer for common dependencies to reduce per-function package size

### DynamoDB

- On-demand billing for unpredictable traffic
- GSIs for user-based lookups (userId-createdAt-index, joinCode-index, vocabSetId-completedAt-index)
- Composite keys for Progress table to enable efficient per-user-per-set queries
- TTL on PracticeSessions (90 days)

### Extraction

- Two-stage pipeline avoids expensive retries: Textract handles OCR reliably, Bedrock handles intelligent extraction
- Bedrock extraction preferred when raw text available (handles free-text layouts better than Textract table parsing)
- Multi-page support: ADD for itemCount to accumulate across multiple image extractions

## Request/Response Models

### Upload

```json
// POST /vocab/upload - Request
{
  "fileName": "workbook_page.jpg",
  "contentType": "image/jpeg",
  "vocabSetId": "uuid"  // optional - adds to existing set
}

// Response
{
  "vocabSetId": "uuid",
  "uploadUrl": "presigned-s3-url",
  "imageKey": "images/{userId}/{vocabSetId}/{timestamp}-original.jpg",
  "expiresIn": 300
}
```

### Extraction

```json
// POST /vocab/process - Request
{
  "vocabSetId": "uuid",
  "imageKey": "s3-key"  // optional, fetched from DB if missing
}

// Response
{
  "vocabSetId": "uuid",
  "status": "review",
  "itemCount": 24,
  "extractionMethod": "bedrock_from_text"
}

// GET /vocab/extraction/{vocabSetId} - Response
{
  "vocabSetId": "uuid",
  "status": "review",
  "itemCount": 24,
  "items": [
    {
      "itemId": "uuid",
      "source": "das Haus",
      "target": "la maison",
      "notes": "",
      "confidence": 90,
      "order": 1
    }
  ]
}
```

### Practice

```json
// POST /practice/start - Request
{
  "vocabSetId": "uuid",
  "direction": "de-fr",
  "questionCount": 20
}

// Response
{
  "sessionId": "uuid",
  "vocabSetId": "uuid",
  "direction": "de-fr",
  "totalQuestions": 20,
  "questions": [
    {
      "questionId": "uuid",
      "itemId": "uuid",
      "question": "das Haus",
      "correctAnswer": "la maison",
      "questionNumber": 1,
      "totalQuestions": 20
    }
  ]
}

// POST /practice/complete - Response (includes error patterns)
{
  "sessionId": "uuid",
  "score": 85,
  "correct": 17,
  "total": 20,
  "duration": 245,
  "detailedResults": [...],
  "leagueUpdate": { ... },
  "errorPatterns": {
    "articleErrors": [
      {"word": "la maison", "yourArticle": "le", "correctArticle": "la"}
    ],
    "repeatedErrors": [
      {"word": "l'école", "timesWrong": 4, "lastAnswers": ["le ecole", "lecole", "l'ecole"]}
    ],
    "summary": "Artikel-Fehler bei 1 Wort — achte auf das grammatische Geschlecht! 1 Wörter bereiten dir wiederholt Schwierigkeiten: l'école"
  }
}
```

### League

```json
// POST /league - Request (teacher only)
{
  "name": "Klasse 9b Französisch",
  "scoreMode": "weekly"
}

// POST /league/join - Request
{
  "joinCode": "ABC123"
}

// GET /league/{leagueId}/leaderboard - Response
{
  "leagueId": "uuid",
  "scoreMode": "weekly",
  "leaderboard": [
    {
      "userId": "...",
      "displayName": "Max M.",
      "score": 42,
      "currentStreak": 5,
      "role": "student",
      "rank": 1
    }
  ]
}
```
