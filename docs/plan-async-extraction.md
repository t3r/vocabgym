# Plan: Asynchrone Vokabel-Extraktion (SQS + Worker)

## Problem

`POST /vocab/process` führt Textract + Bedrock **synchron** in der API-Gateway-
Request aus (15–20 s pro Bild, in Prod bis 19,9 s gemessen). Das reißt bei
mehreren Bildern das harte **API-Gateway-29s-Limit** und den 30s-Axios-Timeout
→ „network error". Bei 10+ Bildern garantiert kaputt. Die Extraktion muss vom
Request entkoppelt asynchron laufen.

## Entscheidungen (mit dem Nutzer abgestimmt)

- **Muster B**: SQS-Queue + Worker-Lambda (kontrollierte Parallelität, Retry, DLQ).
- **Fortschritt pro Set (2a)**: Zähler `pagesTotal`/`pagesDone`/`pagesFailed`.
- **Teil-Fehler (3a)**: Set geht trotzdem in `review`, Fehlseiten via `pagesFailed`
  markiert; nur wenn **alle** Seiten scheitern → `failed`.
- **Benachrichtigung 1+2**: `/vocab/process` kehrt sofort zurück (`202`); Frontend
  pollt Live-Fortschritt „X von Y" + Auto-Redirect; Dashboard-Karten-Badge als
  Fallback.
- **E-Mail-Benachrichtigung (3)**: **Backlog**, nicht in diesem Plan.
- Worker-Concurrency 3–5 (Bedrock-Throttling vermeiden). Guardrail-Block eines
  Bildes zählt als `pagesFailed`. Rate-Limit künftig **pro Bild** (Kosten fallen
  pro Bild an).
- Migrationsfrei für bestehende Sets.

## Zielarchitektur

```
Frontend --POST /vocab/process--> extraction_handler (Enqueuer)
   Enqueuer: Ownership + Rate-Limit/Bild, pagesTotal setzen, N SQS-Nachrichten,
             sofort 202 {vocabSetId, status:'processing', pagesTotal}
   SQS ExtractionQueue --> ExtractionWorker (BatchSize klein, Concurrency 3-5)
             Worker: Textract+Bedrock je Bild, atomar pagesDone/pagesFailed++,
                     bei Abschluss review (pagesDone>0) sonst failed; idempotent
   DLQ nach maxReceiveCount=3
Frontend --GET /vocab/extraction/{id} (poll)--> Zähler X von Y + Auto-Redirect
Dashboard-Karten: Badge aus extractionStatus (⏳/✅/⚠️)
```

## Tasks

- **Task 1 — Infra**: `ExtractionQueue` (SQS) + `ExtractionDLQ` (RedrivePolicy,
  maxReceiveCount 3), VisibilityTimeout ≥ 6× Worker-Timeout (Worker 300s →
  1800s). `ExtractionWorkerFunction` (SQS-Event, BatchSize 1, reserved/maximum
  concurrency 3–5, Timeout 300s, Mem 1024), gleiche Env/IAM wie ExtractionHandler
  + SQS-Rechte. `QUEUE_URL` am extraction_handler + `sqs:SendMessage`.
- **Task 2 — Datenmodell**: VocabSet-Felder `pagesTotal`/`pagesDone`/`pagesFailed`
  (Default 0). Atomarer ADD-Increment-Helper. Migrationsfrei.
- **Task 3 — Enqueuer**: `handle_process` sendet N SQS-Nachrichten
  `{vocabSetId,userId,imageKey,targetLanguage}`, setzt Zähler + Status
  `processing`, gibt `202` zurück. Rate-Limit pro Bild.
- **Task 4 — Worker**: bestehende Extraktionslogik pro Record, atomare Zähler,
  Abschluss review/failed, Idempotenz gegen Doppelzustellung, Guardrail/Fehler
  → pagesFailed, transiente Fehler → raise → SQS-Retry → DLQ.
- **Task 5 — GET erweitern**: `handle_get_extraction` gibt Zähler zurück.
- **Task 6 — Frontend**: `/vocab/process` nicht abwarten; Poll liest Zähler,
  zeigt „Seite X von Y", Auto-Redirect; Dashboard-Karten-Badge.
- **Task 7 — Doku/Steering** + finale Verifikation + Commits.

## Backlog

- **E-Mail-Benachrichtigung (SES)**, wenn ein Set review-bereit ist — für Fälle,
  in denen die Verarbeitung lange dauert und der Nutzer weggeht.
