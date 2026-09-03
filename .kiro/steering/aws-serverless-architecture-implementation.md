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
             ├──────────► Lambda: league_handler
             ├──────────► Lambda: polly_handler
             └──────────► Lambda: goal_handler

  S3 (images/ upload) ──► EventBridge ──► Lambda: icon_handler (robohash identicons)

  POST /vocab/process ──► extraction_handler (enqueuer, 202) ──► SQS ExtractionQueue
                                                                      │ (DLQ after 3 tries)
                                                                      ▼
                                                        Lambda: extraction_worker
                                                        (Textract + Bedrock per image)
                          │
                          ├──────► DynamoDB (9 tables)
                          ├──────► S3 Bucket (Images)
                          ├──────► AWS Textract (OCR)
                          ├──────► Amazon Bedrock (LLM extraction)
                          └──────► Amazon Polly (TTS)
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

**Signup Policy:** `AdminCreateUserOnly = true` — there is **no self-signup**. Teachers onboard new users via `admin_create_user` (Cognito API). New users receive a temporary password by email and must set their own password on first login.

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
- EventBridge: enabled (`EventBridgeConfiguration.EventBridgeEnabled`) so
  `images/` uploads trigger the icon_handler via an EventBridge rule
- Lifecycle policy (per prefix):
  - `images/` — deleted after 30 days (fallback; originals are normally deleted
    by vocab_crud on set approval)
  - `tts/` — deleted after 30 days
  - `identicons/` — **no expiration** (persistent visual identity of a set)
- CORS: Allow PUT/POST/GET from all origins

**Folder Structure:**
```
/images/{userId}/{vocabSetId}/{timestamp}-original.{ext}     # original scan (transient)
/identicons/{userId}/{vocabSetId}/{timestamp}-{set}.png       # robohash icon (set1|set4), persistent
/tts/...                                                       # cached Polly MP3s
```

**Privacy / copyright note:** Original scans are transient. On set approval the
vocab_crud handler deletes all `images/{userId}/{vocabSetId}/*` objects; only the
generated, non-reversible identicon remains. The identicon seed is the S3 object
key (no image bytes), so it has no reproducible relationship to the copyrighted
workbook content.

### 3. Amazon DynamoDB Tables (9 tables)

All tables use on-demand billing (PAY_PER_REQUEST) and are named `vocabtrainer-{tablename}-{stage}`. All 9 tables have Point-in-Time Recovery (PITR) enabled, Project/Environment tags, and DeletionProtection enabled in production.

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
  - sourceLanguage: String (default "de"; prep for non-German source languages)
  - targetLanguage: String (e.g. "fr", "es", "en")
  - extractionStatus: String ("pending" | "processing" | "review" | "approved" | "failed")
  - extractionMethod: String ("textract" | "bedrock_from_text")
  - pagesTotal / pagesDone / pagesFailed: Number (async extraction progress
      counters; the worker atomically ADDs done/failed and finalises the set to
      review/failed when done+failed == total)
  - processedPages: StringSet (image keys already processed — idempotency guard
      against SQS at-least-once redelivery)
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
  - mode: String ("practice" | "exam") — "exam" is the timed exam mode (upward
      timer, no hints/pronunciation, strict scoring); stored per session so the
      history can compare exam runs. Defaults to "practice".
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

#### Table 8: TtsUsage

**Table Name:** `vocabtrainer-tts-usage-{stage}`

```
userId (PK) - String (Cognito sub)
dateKey (SK) - String (ISO date, e.g. "2026-08-29")

Attributes:
  - requestCount: Number (TTS requests made on this date)
  - updatedAt: Number (Unix timestamp)
```

**Purpose:** Rate-limiting for Amazon Polly synthesis requests. The polly_handler increments `requestCount` per user per day and rejects requests that exceed the configured daily limit.

#### Table 9: LearningGoals

**Table Name:** `vocabtrainer-goals-{stage}`

```
goalId (PK) - String (UUID)
userId (SK) - String (Cognito sub of goal owner)

Attributes:
  - title: String
  - vocabSetId: String (target vocab set, optional)
  - leagueId: String (if set by teacher as league-wide goal)
  - targetMasteryLevel: Number (0-5, desired mastery)
  - deadline: String (ISO date)
  - status: String ("on-track" | "at-risk" | "behind" | "expired" | "achieved")
  - createdAt: Number
  - updatedAt: Number

GSI: userId-deadline-index
  Partition Key: userId
  Sort Key: deadline (String)
  Projection: ALL
```

**Purpose:** Learning Goals with deadline and target mastery level. `calculate_goal_status` (in goal_handler) computes progress, pace, and current status. Teachers can create league-wide goals visible to all league members.

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
POST   /league/{leagueId}/invite              → league_handler (create user + add to league)

GET    /users/profile                         → league_handler (get displayName)
PUT    /users/profile                         → league_handler (update displayName)
POST   /users/invite                          → league_handler (onboard user without league)

GET    /tts/voices                            → polly_handler
POST   /tts/synthesize                        → polly_handler

GET    /goals                                 → goal_handler
POST   /goals                                 → goal_handler
GET    /goals/{goalId}                        → goal_handler
PUT    /goals/{goalId}                        → goal_handler
DELETE /goals/{goalId}                        → goal_handler
GET    /goals/{goalId}/members                → goal_handler (league member progress, teacher only)
```

### 5. AWS Lambda Functions (9 functions + SharedLayer)

#### General Configuration

**Runtime:** Python 3.11
**Architecture:** x86_64
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
TTS_USAGE_TABLE=vocabtrainer-tts-usage-{stage}
GOALS_TABLE=vocabtrainer-goals-{stage}
REGION={AWS::Region}
```

**SharedLayer:**
- Layer Name: `vocabtrainer-shared-{stage}`
- Contains shared Python modules under `python/lib/`:
  - `utils.py` — build_response, build_error_response, get_user_id_from_event, generate_uuid, get_timestamp, parse_body, get_path_parameter
  - `validation.py` — validate_uuid, validate_file_upload, validate_practice_options
  - `languages.py` — get_language, DEFAULT_TARGET_LANGUAGE, language config (name, nameEnglish per code)
  - `auth.py` — auth utilities
- Compatible with python3.11 and x86_64

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

**Purpose:** Asynchronous two-stage vocabulary extraction: Textract OCR → Bedrock
LLM extraction. **The heavy work is decoupled from the API request via SQS** so
multi-image uploads never hit the API Gateway 29s limit.

**Async architecture:**
- `POST /vocab/process` is an **enqueuer**: verifies ownership, applies the
  per-image daily rate limit, initialises the set's page counters
  (`pagesTotal`/`pagesDone`/`pagesFailed`), sets status `processing`, sends
  **one SQS message per image** to `ExtractionQueue`, and returns **202** with
  `{vocabSetId, status:'processing', pagesTotal}` immediately.
- `ExtractionWorkerFunction` (handler `worker.lambda_handler`, SQS-triggered,
  BatchSize 1, MaximumConcurrency 5 to avoid Bedrock throttling) consumes the
  queue. Per message it runs `process_single_image` (the Textract+Bedrock
  pipeline below) and then `record_page_result`, which atomically ADDs
  `pagesDone`/`pagesFailed` and finalises the set to `review` (≥1 page produced)
  or `failed` (all pages failed). Idempotent against SQS at-least-once redelivery
  via a `processedPages` string-set claim.
- `ExtractionQueue` VisibilityTimeout = 1800s (6× worker timeout); failures
  redrive to `ExtractionDLQ` after `maxReceiveCount: 3`.
- `GET /vocab/extraction/{vocabSetId}` returns the page counters so the frontend
  shows live "Seite X von Y" progress and the dashboard shows a status badge.
- Partial failures keep the set reviewable (successful pages preserved).

**Extraction Pipeline (per image, in the worker):**

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

3. **Store results:** Batch write VocabItems to DynamoDB. Update VocabSet itemCount (ADD for multi-page support).

**Guardrail + Converse call structure:** The developer instructions and the
untrusted OCR data are sent as **separate content blocks**; only the OCR data is
tagged with the `guard_content` qualifier so the PROMPT_ATTACK filter evaluates
just the user data (developer prompt exempt). The guardrail's **content filters
are INPUT-only** (`OutputStrength: NONE`) because the model output is structured
vocabulary JSON — output moderation only produced false positives (e.g.
MISCONDUCT blocking harmless vocab). Guardrail trace is enabled and logged on
`guardrail_intervened`.

```python
bedrock_client.converse(
    modelId='eu.amazon.nova-pro-v1:0',
    messages=[{'role': 'user', 'content': [
        {'text': instruction},
        {'guardContent': {'text': {'text': ocr_data, 'qualifiers': ['guard_content']}}},
    ]}],
    inferenceConfig={'maxTokens': 4096},
    guardrailConfig={'guardrailIdentifier': ..., 'guardrailVersion': ..., 'trace': 'enabled'},
)
```

**IAM Permissions (handler + worker):**
- S3: GetObject on images bucket
- DynamoDB: CRUD on VocabSets, VocabItems
- Textract: AnalyzeDocument, DetectDocumentText
- Bedrock: InvokeModel on foundation-model/* and inference-profile/*, ApplyGuardrail
- Handler additionally: `sqs:SendMessage` to ExtractionQueue; Worker: SQS consume via event mapping

**Note:** Extraction prompts are stored in SSM Parameter Store and can be updated without redeployment. The learning-tips prompt (progress_handler/learning_tips.py) is deliberately kept IN CODE, not in SSM: it is tightly coupled to the cluster data structure it interpolates and, critically, carries the anti-hallucination guardrails (feed only the vetted rule from canonical_tip; forbid inventing a word's gender or literal translations). Those constraints are pinned by unit tests against the code string, so the prompt must not be made freely editable in SSM where the safety wording could be removed without a failing test.

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

**Purpose:** Manage practice sessions with smart repetition, answer validation, error pattern tracking, and league stat updates. Sessions run in one of two modes: `practice` (default; hints, pronunciation, "close" answers let the user decide) or `exam` (timed mode — the client shows an upward timer, hints/pronunciation are disabled, and "close" answers count strictly as wrong). The chosen `mode` is stored on the session and returned by start/complete so the history can compare exam runs.

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

#### Function 7: polly_handler

**Function Name:** `vocabtrainer-polly-handler-{stage}`
**Trigger:** GET /tts/voices, POST /tts/synthesize

**Purpose:** Amazon Polly text-to-speech synthesis for target-language vocabulary words. MP3 results are cached in S3 to avoid redundant Polly calls. Usage is rate-limited per user per day via the TtsUsage table.

**Operations:**

- **GET /tts/voices** — Returns available Polly voices grouped by language code. Results list voices suitable for the supported target languages (fr, en, es, it).
- **POST /tts/synthesize** — Accepts `{text, languageCode, voiceId}`. Checks S3 cache first (key derived from text + voiceId hash). On cache miss, calls Polly Standard engine, stores MP3 in S3, returns presigned URL. Increments `requestCount` in TtsUsage; rejects with 429 if daily limit exceeded.

**Key Details:**
- Only the **target-language word** is synthesized (never the German source word).
- MP3 cache key is stored under a `tts/` prefix in the images bucket.
- Rate-limit check: reads TtsUsage item for `{userId, dateKey}` and enforces a configured daily maximum.

**IAM Permissions:**
- Polly: `polly:SynthesizeSpeech`, `polly:DescribeVoices`
- S3: PutObject, GetObject on images bucket (tts/ prefix)
- DynamoDB: CRUD on TtsUsage table

#### Function 8: goal_handler

**Function Name:** `vocabtrainer-goal-handler-{stage}`
**Trigger:** GET/POST /goals, GET/PUT/DELETE /goals/{goalId}, GET /goals/{goalId}/members

**Purpose:** Manage Learning Goals (Lernziele) with deadlines and target mastery levels. Tracks progress and pace per student and per league.

**Operations:**

- **GET /goals** — List all goals for the authenticated user.
- **POST /goals** — Create a new goal with `{title, vocabSetId, deadline, targetMasteryLevel}`. Teachers may also set `leagueId` for a league-wide goal.
- **GET /goals/{goalId}** — Get goal details including computed `status`, `currentMastery`, pace analysis, and a `perSet` breakdown (each entry carries the vocab set `title`, resolved from VocabSets, plus per-set progress) so the UI shows set names rather than ids.
- **PUT /goals/{goalId}** — Update goal parameters (deadline, targetMasteryLevel, title).
- **DELETE /goals/{goalId}** — Remove a goal.
- **GET /goals/{goalId}/members** — Teacher-only. Returns per-member progress for a league-wide goal.

**`calculate_goal_status` logic:**
- Computes current average mastery for the target vocabSet
- Compares against deadline and `targetMasteryLevel`
- Returns one of: `on-track`, `at-risk`, `behind`, `expired`, `achieved`
- Expired goals (past deadline, not achieved) remain visible in history

**IAM Permissions:**
- DynamoDB: CRUD on LearningGoals; Read on Progress, VocabSets, VocabItems, Leagues, LeagueMembers, Users

#### Function 9: icon_handler

**Function Name:** `vocabtrainer-icon-handler-{stage}`
**Memory:** 1024 MB
**Timeout:** 60 seconds
**Trigger:** EventBridge rule on S3 `Object Created` events under the `images/` prefix (NOT API Gateway).

**Purpose:** Generate a deterministic robohash identicon for every uploaded
workbook page, so the copyrighted original scan can be replaced by a
non-reversible generated image. This is the ONLY function carrying the
`Pillow` + `robohash` dependency (fully decoupled from the other handlers).

**Flow:**
1. S3 upload under `images/` → bucket emits event to the default EventBridge bus
   (`EventBridgeEnabled: true`) → EventBridge rule (prefix `images/`) invokes
   this function. EventBridge (not a direct S3→Lambda notification) is used to
   avoid a circular CFN dependency and to filter by prefix.
2. Seed = `sha256(full image key)` → one unique icon per page. No image bytes are
   read, so the icon has no reproducible link to the workbook content.
3. Renders BOTH styles — `set1` (Classic Robots) and `set4` (Cats) — at 256px and
   writes them to `identicons/{userId}/{vocabSetId}/{timestamp}-{set}.png`, so a
   user switching their `identiconSet` preference sees the change instantly.
4. Idempotent (`head_object` skip) and loop-guarded (never reacts to writes under
   `identicons/` or non-`images/` prefixes). A single failure never fails the batch.

**Robohash licensing:** code MIT; artwork CC-BY-3.0/4.0 (set1 Zikri Kader, set4
David Revoy). Attribution is provided in the README.

**IAM Permissions:**
- S3: GetObject, PutObject scoped to the `identicons/*` prefix only (never reads originals)

**Related pieces:**
- vocab_crud `handle_update` deletes the original scans on approval and serves the
  identicon presigned URLs (per page) on GET/list.
- The user's style choice is stored in `Users.preferences.identiconSet`
  (`set1`|`set4`) via `PUT /users/profile`.

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

### 8. Amazon Polly

**Purpose:** Text-to-speech synthesis for target-language vocabulary words in practice and review.

**Integration:** Called by polly_handler. Synthesized MP3 audio is cached in S3 (under `tts/` prefix) and served via presigned URLs to avoid repeated Polly calls for the same word/voice combination.

**Voices:** `GET /tts/voices` returns voices grouped by language code (fr, en, es, it); voice and accent are selectable per student preference (persisted to localStorage).

**Rate limiting:** Daily per-user request count tracked in the TtsUsage DynamoDB table.

### 9. Amazon CloudFront

**Distribution for frontend SPA.**

**Origin:** S3 bucket via Origin Access Control (OAC), not OAI.

**Configuration:**
- Default root object: `index.html`
- Viewer protocol: Redirect HTTP to HTTPS
- Compress: Yes
- Price class: PriceClass_100 (US, Canada, Europe)
- Custom error responses: 403 → /index.html (200), 404 → /index.html (200) — for SPA routing

**Custom Domain:** Production frontend served at **vocab.gym.t3r.de** via CloudFront + Route 53 + ACM (certificate in us-east-1). Custom domain parameters (`CERTIFICATE_ARN`, `HOSTED_ZONE_ID`) are passed to the CloudFormation stack during deployment.

### 10. CloudWatch Logging & Monitoring

**Log Groups:**
- `/aws/lambda/vocabtrainer-upload-handler-{stage}`
- `/aws/lambda/vocabtrainer-extraction-handler-{stage}`
- `/aws/lambda/vocabtrainer-vocab-crud-handler-{stage}`
- `/aws/lambda/vocabtrainer-practice-handler-{stage}`
- `/aws/lambda/vocabtrainer-progress-handler-{stage}`
- `/aws/lambda/vocabtrainer-league-handler-{stage}`
- `/aws/lambda/vocabtrainer-polly-handler-{stage}`
- `/aws/lambda/vocabtrainer-goal-handler-{stage}`

**Retention:** 7 days (dev), 90 days (prod)

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

### 11. Backup & Disaster Recovery

**DynamoDB PITR:** All 9 tables have Point-in-Time Recovery enabled. Allows restore to any second within the last 35 days.

**DeletionProtection:** Enabled on all 9 tables in production to prevent accidental deletion.

**AWS Backup:**
- Backup vault: `vocabtrainer-backup-vault-{stage}`
- Tag-based selection — all resources tagged `Project=VocabTrainer` are included
- **Dev plan:** Daily backups, 7-day retention
- **Prod plan:** Daily backups (35-day retention) + weekly backups (90-day retention)

**Restore Testing (prod only):**
- SSM Automation runbook runs weekly (PITR) and monthly (AWS Backup source) to verify recoverability
- An SNS topic + EventBridge rule alerts on runbook failures

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
│   ├── polly_handler/
│   │   ├── app.py
│   │   └── requirements.txt
│   └── goal_handler/
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
- File upload: JPG, PNG only (HEIC rejected); max 10 MB. The S3 key extension is
  whitelisted to {jpg, jpeg, png} (fallback jpg) so a crafted name like
  `evil.jpg.exe` cannot place an unexpected extension in the object key.

### Abuse / Cost Protection

- **Extraction rate limit:** the extraction handler enforces a per-user daily
  cap (`ExtractionUsageTable`, atomic counter) and returns 429 before the
  expensive Textract/Bedrock calls — prevents DoS-by-cost and delete/recreate abuse.
- **TTS rate limit:** the polly handler enforces a per-user hourly cap (`TtsUsage`).
- **Owned-set counter:** `lib/plans.py` maintains a race-safe `ownedSetCount` on
  the Users record (atomic conditional increment) so plan set-limits cannot be
  bypassed by concurrent requests. Enforcement is gated by `ENFORCE_SET_LIMITS`.

### LLM Safety (extraction)

- **Prompt-injection hardening:** untrusted OCR text is length-capped and wrapped
  in an `<ocr_data>` block with a standing instruction to ignore any instructions
  inside it; breakout delimiters are stripped.
- **Bedrock Guardrail:** a managed guardrail (content filters SEXUAL/VIOLENCE=HIGH,
  HATE/INSULTS/MISCONDUCT=MEDIUM, PROMPT_ATTACK=HIGH input-only) is applied to the
  extraction converse calls. On `stopReason == 'guardrail_intervened'` the handler
  returns no vocabulary (fail-safe) so blocked content is never stored.

### Access control / no information disclosure

- `vocab_crud` `GET /vocab/{id}` resolves access as: owned-by-caller first, else
  the set must be assigned to the caller's league (fetched deterministically by
  the league's teacher owner). Every access failure returns a uniform **404**
  (never 403, never a cross-owner scan) so set IDs cannot be probed for existence.

### Billing (future `billing_handler`) — REQUIREMENT

- The Stripe webhook endpoint (`POST /billing/webhook`) MUST be configured
  **without** the Cognito authorizer and MUST verify the `Stripe-Signature`
  header against the webhook signing secret (from SSM/Secrets Manager) as its
  first operation, before processing the event. Without signature verification
  anyone could forge plan upgrades. (Not yet implemented — billing_handler pending.)

### DynamoDB Decimal Handling

DynamoDB returns numbers as `Decimal` type in Python. Always use `json.dumps(data, default=str)` to serialize responses. This is enforced across all handlers.

## Performance Optimization

### Lambda

- x86_64 architecture
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
  "imageKey": "s3-key"  // optional; if omitted, ALL pages of the set are processed
}

// Response — 202 Accepted (async; work continues in the worker)
{
  "vocabSetId": "uuid",
  "status": "processing",
  "pagesTotal": 3
}

// GET /vocab/extraction/{vocabSetId} - Response (polling source)
{
  "vocabSetId": "uuid",
  "status": "review",
  "itemCount": 24,
  "pagesTotal": 3,
  "pagesDone": 3,
  "pagesFailed": 0,
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
  "questionCount": 20,
  "mode": "practice"  // "practice" (default) or "exam" (timed)
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
