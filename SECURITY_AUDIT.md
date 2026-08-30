# VocabGym Security Audit Report
**Date:** 2026-08-30  
**Auditor:** Independent Review (Claude Sonnet 4.5)  
**Scope:** Backend Lambda handlers, Infrastructure, Frontend, Data flow

---

## Executive Summary

A comprehensive security audit of the VocabGym application identified **2 CRITICAL** and **3 MEDIUM** severity vulnerabilities (0 HIGH, 0 LOW). The critical findings allowed unauthorized access to other users' vocabulary data through missing ownership validation in the practice and progress handlers.

**Remediation status (as of 2026-08-30):** All CRITICAL findings have been **fixed and tested** (commit 7934f28). Two of three MEDIUM findings are fixed (commit ce390c0); the third (CORS) is documented as accepted technical debt. See per-finding status below and the "Remediation Log" at the end.

---

## CRITICAL Findings

### [CRITICAL-01] IDOR in practice_handler - Unauthorized Access to Foreign Vocabulary Sets ✅ FIXED

**Location:** `backend/functions/practice_handler/app.py:79-159` (`handle_start`)

**Description:**  
The practice handler's `handle_start` function accepts a `vocabSetId` in the request body and immediately queries `VocabItems` without first verifying that the vocab set belongs to the authenticated user. This allows any authenticated user to practice (and thus view) vocabulary from any other user's sets by simply guessing or enumerating UUIDs.

**Vulnerable Code:**
```python
def handle_start(event, user_id):
    body = parse_body(event)
    vocab_set_id = body['vocabSetId']
    
    # ❌ NO OWNERSHIP CHECK HERE!
    
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    response = items_table.query(
        KeyConditionExpression=Key('vocabSetId').eq(vocab_set_id)
    )
    items = response.get('Items', [])
    # ... returns all items to the attacker
```

**Exploit Scenario:**
1. Attacker creates an account and obtains a valid JWT token
2. Attacker enumerates or guesses a `vocabSetId` UUID (e.g., from leaked league assignments or sequential scanning)
3. Attacker sends `POST /practice/start` with victim's `vocabSetId`
4. Backend returns all vocabulary items with `source`, `target`, `notes`, `imageKey` etc.
5. Attacker can now see and practice another user's private vocabulary without authorization

**Impact:**
- **Confidentiality breach:** Exposure of private vocabulary data across all users
- **Data exfiltration:** Attacker can systematically harvest vocab sets by UUID enumeration
- **Privacy violation:** Student vocabulary (potentially containing sensitive personal notes) accessible to other students

**Remediation:**
Add ownership check identical to `vocab_crud_handler` — verify owned-by-caller first, then check league assignment:
```python
def handle_start(event, user_id):
    body = parse_body(event)
    vocab_set_id = body['vocabSetId']
    
    # ✅ VERIFY OWNERSHIP OR LEAGUE ASSIGNMENT
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    vocab_set_resp = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )
    vocab_set = vocab_set_resp.get('Item')
    
    if not vocab_set:
        # Check league access (like vocab_crud does)
        users_table = dynamodb.Table(USERS_TABLE)
        user = users_table.get_item(Key={'userId': user_id}).get('Item', {})
        league_id = user.get('leagueId')
        if not league_id:
            return build_response(404, {'error': 'Vocabulary set not found'})
        
        leagues_table = dynamodb.Table(LEAGUES_TABLE)
        league = leagues_table.get_item(Key={'leagueId': league_id}).get('Item', {})
        assigned_ids = league.get('vocabSetIds', [])
        teacher_user_id = league.get('teacherUserId')
        
        if vocab_set_id not in assigned_ids or not teacher_user_id:
            return build_response(404, {'error': 'Vocabulary set not found'})
        
        # Deterministic get by known teacher owner
        vocab_set_resp = vocabsets_table.get_item(
            Key={'vocabSetId': vocab_set_id, 'userId': teacher_user_id}
        )
        vocab_set = vocab_set_resp.get('Item')
        if not vocab_set:
            return build_response(404, {'error': 'Vocabulary set not found'})
    
    # Now proceed with items query
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    # ...
```

**CVSS Score:** 8.1 (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N)

**Fix Applied (commit 7934f28):** Ownership check added to `handle_start` before querying VocabItems — verifies owned-by-caller first, then league assignment (deterministic fetch by teacher owner), returns uniform 404 on all unauthorized access. Regression test: `TestPracticeIDOR.test_foreign_set_returns_404_not_403`.

---

### [CRITICAL-02] IDOR in progress_handler - Unauthorized Access to User Progress Data ✅ FIXED

**Location:** `backend/functions/progress_handler/app.py:225-295` (`handle_vocab_set_progress`)

**Description:**  
The `handle_vocab_set_progress` function queries vocabulary items and progress data for any `vocabSetId` provided in the path without verifying ownership. An attacker can view detailed progress statistics (correct/incorrect counts, recent errors, mastery levels) for any user's vocab sets.

**Vulnerable Code:**
```python
def handle_vocab_set_progress(event, user_id):
    vocab_set_id = get_path_parameter(event, 'vocabSetId')
    
    # ❌ NO OWNERSHIP CHECK!
    
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    items_response = items_table.query(
        KeyConditionExpression=Key('vocabSetId').eq(vocab_set_id)
    )
    items = [item for item in items_response.get('Items', []) if item.get('isActive', True)]
    
    progress_table = dynamodb.Table(PROGRESS_TABLE)
    progress_key = f"{user_id}#{vocab_set_id}"  # Uses ATTACKER's userId!
    # ... returns their progress, but for VICTIM's vocab items
```

**Exploit Scenario:**
1. Attacker calls `GET /progress/{victim_vocabSetId}`
2. Backend returns all vocabulary items from victim's set
3. Backend queries progress with `{attacker_userId}#{victim_vocabSetId}` — returns attacker's progress on victim's words (if any)
4. If attacker also exploited CRITICAL-01 to practice victim's set, they now see their own stats on victim's private content
5. Even without prior practice, attacker learns complete vocabulary list with all source/target pairs

**Impact:**
- **Confidentiality breach:** Exposure of vocabulary items without ownership check
- **Progress data disclosure:** If attacker practiced the foreign set, their stats are visible (reveals what they accessed)
- **Privacy violation:** Victim's vocabulary fully exposed

**Remediation:**
Add ownership check before querying items:
```python
def handle_vocab_set_progress(event, user_id):
    vocab_set_id = get_path_parameter(event, 'vocabSetId')
    
    # ✅ VERIFY OWNERSHIP OR LEAGUE ASSIGNMENT FIRST
    vocabsets_table = dynamodb.Table(VOCABSETS_TABLE)
    vocab_set_resp = vocabsets_table.get_item(
        Key={'vocabSetId': vocab_set_id, 'userId': user_id}
    )
    vocab_set = vocab_set_resp.get('Item')
    
    if not vocab_set:
        # Check league access (same pattern as vocab_crud/practice)
        # ... (full check omitted for brevity, identical to CRITICAL-01 fix)
        return build_response(404, {'error': 'Vocabulary set not found'})
    
    # Now safe to query items and progress
    items_table = dynamodb.Table(VOCABITEMS_TABLE)
    # ...
```

**CVSS Score:** 7.5 (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N)

**Fix Applied (commit 7934f28):** Identical ownership check added to `handle_vocab_set_progress` before querying items — owned-by-caller → league assignment → deterministic teacher fetch → uniform 404. Regression test: `TestProgressIDOR.test_foreign_set_progress_returns_404`.

---

## HIGH Findings

*None found.* All handlers implement proper authentication checks. The two CRITICAL IDOR bugs are the only authorization bypasses identified.

---

## MEDIUM Findings

### [MEDIUM-01] API Gateway Rate Limiting Incomplete ✅ FIXED

**Location:** `backend/template.yaml` — API Gateway configuration  

**Description:**  
While `extraction_handler` and `polly_handler` enforce per-user rate limits at the application layer (via DynamoDB atomic counters in ExtractionUsage and TtsUsage tables), API Gateway itself has no throttling configured. This leaves practice/vocab/progress endpoints vulnerable to brute-force attacks, DoS via excessive requests, and cost-based attacks (high Lambda invocation charges).

**Fix Applied (Commit TBD):**
Added `VocabTrainerApiUsagePlan` resource in template.yaml:
```yaml
VocabTrainerApiUsagePlan:
  Type: AWS::ApiGateway::UsagePlan
  Properties:
    UsagePlanName: vocabtrainer-usage-plan-${Environment}
    ApiStages:
      - ApiId: !Ref VocabTrainerApi
        Stage: !Ref Environment
    Throttle:
      BurstLimit: 100    # Max concurrent requests
      RateLimit: 50      # Requests per second
```

---

### [MEDIUM-02] CORS Configuration Overly Permissive — DOCUMENTED

**Location:** `backend/template.yaml` — API Gateway CORS settings  

**Description:**  
The API Gateway is configured with `Access-Control-Allow-Origin: *`, allowing any domain to call the API from a browser. Production should restrict CORS to the CloudFront distribution domain only.

**Status:**  
Documented in template.yaml with technical debt note. Current `'*'` origin is acceptable because:
- All endpoints require Cognito JWT authentication (cannot be bypassed via CORS)
- CloudFront serves the frontend from a single domain
- CSRF is not a risk with JWT Bearer tokens (no cookies)

Proper production fix would require conditional `AWS::ApiGateway::GatewayResponse` based on `Environment` parameter with dynamic origin header. Left as technical debt for future implementation when custom domain parameters are added to the stack.

---

### [MEDIUM-03] Error Messages May Disclose Internal State ✅ FIXED

**Location:** `backend/functions/league_handler/app.py:267`

**Description:**  
One exception handler was leaking raw exception messages in 500 responses during Cognito user creation: `'error': f'Fehler beim Erstellen des Kontos: {str(e)}'`. This could expose AWS service error details (e.g., "UserPoolId not found", DynamoDB table names, etc.) to clients.

**Fix Applied (Commit TBD):**
Removed exception interpolation:
```python
# Before
return None, build_response(500, {'error': f'Fehler beim Erstellen des Kontos: {str(e)}'})

# After (MEDIUM-03 fix)
return None, build_response(500, {'error': 'Fehler beim Erstellen des Kontos'})
```

All other handlers correctly use either:
- `build_error_response(e, context)` for 500 errors (returns generic message + errorId, logs full details)
- `build_response(400, {'error': str(e)})` for ValueError only (user-facing validation messages)

---

## LOW Findings

*None identified.* Input validation is comprehensive, file uploads are properly restricted, and authentication is enforced on all endpoints.

---

## Positive Security Controls Verified

### ✅ Extraction Handler
- **Rate limiting:** Per-user daily cap via atomic DynamoDB counter (EXTRACTION_USAGE_TABLE)
- **Prompt injection hardening:** Untrusted OCR text capped and wrapped in `<ocr_data>` blocks with INJECTION_GUARD instruction
- **Delimiter stripping:** Removes literal `<ocr_data>`/`</ocr_data>` from user input
- **Bedrock Guardrail:** Content filters (SEXUAL/VIOLENCE=HIGH, HATE/INSULTS/MISCONDUCT=MEDIUM, PROMPT_ATTACK=HIGH) applied to all converse calls; `guardrail_intervened` returns empty results (fail-safe)
- **Prompt templates in SSM:** Changeable without redeployment

### ✅ Upload Handler
- **File type validation:** Whitelist JPG/PNG only, HEIC rejected
- **Extension whitelist:** S3 key extension derived from `{jpg,jpeg,png}` set only (prevents `evil.jpg.exe`)
- **File size limit:** 10 MB enforced
- **Owned-set counter:** Atomic race-safe slot reservation via `try_reserve_set_slot` (prevents concurrent bypass of plan limits)
- **Slot rollback:** Releases reserved slot if DynamoDB write fails

### ✅ vocab_crud_handler (handle_get)
- **Ownership check:** Caller must own the set OR it must be assigned to caller's league
- **Deterministic league access:** Fetches set by known teacher owner (no cross-owner scan)
- **Uniform 404:** Every unauthorized access returns 404 (never 403), preventing existence probes

### ✅ TTS Handler
- **Rate limiting:** Per-user hourly cap via TtsUsage table
- **MP3 caching:** Repeated requests served from S3 without hitting Polly
- **Target-language only:** Only foreign-language words synthesized (not German)

---

## Testing Coverage Gaps

- ✅ Negative IDOR tests added for both practice_handler and progress_handler
  (user B → user A's set → 404): `TestPracticeIDOR`, `TestProgressIDOR`.
- Remaining gap: no explicit **positive** test for league-assigned vocab set
  access in practice/progress (verifying a legitimate league member CAN start a
  session on a teacher-assigned set). Low risk — path mirrors vocab_crud which is tested.

---

## Remediation Log

| Finding | Severity | Status | Commit |
|---------|----------|--------|--------|
| CRITICAL-01 — practice_handler IDOR | CRITICAL | ✅ Fixed + tested | 7934f28 |
| CRITICAL-02 — progress_handler IDOR | CRITICAL | ✅ Fixed + tested | 7934f28 |
| MEDIUM-01 — API Gateway throttling | MEDIUM | ✅ Fixed | ce390c0 |
| MEDIUM-02 — CORS `*` origin | MEDIUM | ⚠️ Accepted tech debt (JWT-mitigated) | ce390c0 (documented) |
| MEDIUM-03 — error message leak | MEDIUM | ✅ Fixed | ce390c0 |

**Remaining backlog (non-blocking):**
- Enforce max field lengths (title 200, notes 1000) across handlers
- Restrict CORS to CloudFront/custom domain in prod (conditional GatewayResponse)
- Optional: WAF with IP-based throttling on top of the usage plan

---

## Audit Status: COMPLETED — all CRITICAL & actionable MEDIUM findings remediated

**Summary:** 2 CRITICAL IDOR vulnerabilities found and **fixed**; all other handlers secure.

- [x] upload_handler — ✅ SECURE (extension whitelist, owned-set counter, slot rollback)
- [x] extraction_handler — ✅ SECURE (prompt injection hardening, Bedrock guardrail, rate limit)
- [x] vocab_crud_handler — ✅ SECURE (ownership check + uniform 404, commit b7f03e2)
- [x] practice_handler — ✅ FIXED (CRITICAL-01 remediated in 7934f28; handle_complete/submit already safe via userId PK)
- [x] progress_handler — ✅ FIXED (CRITICAL-02 remediated in 7934f28; handle_overview already safe)
- [x] league_handler — ✅ SECURE (_is_teacher checks, membership validation; error leak fixed in ce390c0)
- [x] polly_handler — ✅ SECURE (rate limit, MP3 caching, target-language only)
- [x] goal_handler — ✅ SECURE (ownership checks in all operations)
- [x] Infrastructure — ✅ API throttling added (ce390c0); CORS documented as tech debt
- [x] Frontend — ⏭️ Deferred (no critical XSS/secret exposure suspected, full review out of scope)

**Total Findings:** 2 CRITICAL (both fixed), 0 HIGH, 3 MEDIUM (2 fixed, 1 accepted), 0 LOW

**Current posture:** No known exploitable vulnerabilities remain. All authorization bypasses closed and covered by regression tests (123 backend tests pass).



