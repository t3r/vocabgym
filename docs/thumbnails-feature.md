# AI Comic Thumbnails (practice) — operational notes

Generates a comic-style thumbnail illustrating each vocabulary word's meaning,
shown in the practice QuestionCard (learning mode only — hidden in exam mode,
since a picture of the meaning is a hint).

## Pipeline (two-stage, decoupled via SQS)

```
POST /images/thumbnail  ──►  cache hit?  ──► 200 { status: ready, url }   (S3, no LLM)
   (image_handler)             │ miss
                               ▼
                        rate-limit + enqueue ──► 202 { status: pending }
                               │
                               ▼  ThumbnailQueue (DLQ after 3 tries)
                        ThumbnailWorker (functions/thumbnail_worker/):
                          Stage 1  Nova Pro (eu-central-1, Converse)
                                   → short English comic prompt (≤77 chars),
                                     symbolic / object-focused, no text, no people
                          Stage 2  Stable Image Core (us-west-2, InvokeModel)
                                   → image (negative_prompt drops text + people)
                          → downscale to 256px WebP (Pillow)
                          → S3  thumbnails/{sha256(normalized German source)}.png

GET /images/thumbnail/{vocabSetId}/{itemId}  ──►  poll: ready → url, else pending
```

- **One image per MEANING, shared across all languages.** The cache key is
  `sha256(normalized German source)` — no language segment. "das Bad" (→ il
  bagno / la salle de bain / …) generates ONE image reused by every target
  language, set and user. The prompt (Stage 1) is built from the German meaning
  only. This minimises generations further than a per-word/per-language key.
- **Cache = cost control.** A meaning is generated exactly once. The GET/POST
  cache path only does `s3:head_object` — no LLM call. Per-user daily rate limit
  (`ThumbnailUsageTable`, default 60) applies to real generations (misses) only.
- **Small files.** The model returns ~1 MP; the worker downscales to a 256px
  WebP (~10-40 KB) before caching. This does NOT change Bedrock cost (flat per
  image) but cuts S3 transfer + mobile load time by ~100x. The S3 key keeps a
  `.png` suffix for URL stability; the body is WebP (ContentType image/webp).
- **No long-running API Lambda.** The API function only enqueues; the two model
  calls + downscale run in the async worker (Timeout 120s, VisibilityTimeout
  720s = 6×). Pillow lives ONLY in `functions/thumbnail_worker/` so the
  latency-sensitive API handler stays lean.

## Data residency (why us-west-2 is acceptable)

No current (non-legacy) Bedrock image model is available in any EU region
(verified via AWS docs: Nova Canvas EU=eu-west-1 but Legacy; Stability &
Titan Image are US-only). So Stage 2 runs in **us-west-2**.

Crucially, the German/target **vocabulary word never leaves the EU**: Stage 1
(Nova Pro, eu-central-1) turns the meaning into a **generic English motif
prompt** (e.g. "comic style bathroom with bathtub, sink and toilet"). Only that
motif prompt — no personal data, no user vocabulary — is sent to us-west-2. The
generated PNG is stored in the eu-central-1 images bucket.

Model region/id are env-configurable on the worker (`IMAGE_MODEL_ID`,
`IMAGE_MODEL_REGION`, `PROMPT_MODEL_ID`) so switching to a future EU image model
is a one-line change.

## Prerequisites before first deploy

1. **Bedrock model access (per region, in the Bedrock console):**
   - `amazon.nova-pro-v1:0` in **eu-central-1** (already used by extraction).
   - `stability.stable-image-core-v1:1` in **us-west-2** — must be enabled.
   Without model access the worker's InvokeModel fails (AccessDenied) and the
   job goes to the DLQ.

2. **Deploy-role IAM:** add the SQS lifecycle permissions for the thumbnail
   queues — see `docs/deploy-role-thumbnails-permissions.json`. The
   `lambda:*EventSourceMapping` permissions are already granted by
   `docs/deploy-role-async-extraction-permissions.json` (Resource `*`), so they
   also cover the thumbnail worker's SQS mapping.

3. The Lambda execution role for the worker already gets `bedrock:InvokeModel`
   on `arn:aws:bedrock:*::foundation-model/*` (wildcard region covers us-west-2)
   via the SAM template.
