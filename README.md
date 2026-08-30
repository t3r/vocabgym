# VocabGym 💪

Vokabeltrainer für deutsche Gymnasialschüler. Workbook-Seiten scannen, Vokabeln per KI extrahieren, mit smarter Wiederholung üben.

Unterstützte Zielsprachen: 🇫🇷 Französisch · 🇬🇧 Englisch · 🇪🇸 Spanisch · 🇮🇹 Italienisch

## Features

- **KI-Extraktion** — Workbook-Foto hochladen → Textract OCR → Bedrock (Amazon Nova Pro) extrahiert Vokabelpaare automatisch
- **Smart Repetition** — Schwache Wörter erscheinen häufiger, Fehler-Pattern werden erkannt
- **Lernhinweise** — Nach jeder Übung: Artikel-Fehler, wiederholte Schwierigkeiten, personalisierte Tipps
- **Aussprache** — Fremdsprach-Wörter per Amazon Polly anhören; Akzent & Stimme wählbar; neue Wörter werden sofort vorgesagt
- **Lernziele** — Ziele mit Deadline & Mastery-Level, Fortschritts- und Tempo-Tracking (auch pro Liga)
- **Liga-System** — Lehrer erstellen Ligen, Schüler treten per Code bei, Leaderboard mit Streaks 🔥
- **Invite-Only** — Lehrer laden Schüler per E-Mail ein (kein Self-Signup)
- **Dark Mode** — Vollständige Unterstützung
- **Deutsche UI** — Du-Form für Schüler, Sie-Form für Lehrer

## Architektur

→ **[Ausführliches Architekturdiagramm](docs/architecture.md)** (Mermaid)

```
Vue 3 SPA → CloudFront → API Gateway → Lambda (Python 3.11)
                              ↓
              Cognito    DynamoDB (9 Tabellen)    S3
                              ↓
              Textract → Bedrock Nova Pro (Vocab-Extraktion)
              Polly (Aussprache, MP3-Cache in S3)
```

| Schicht | Technologie |
|---------|-------------|
| Frontend | Vue 3, Tailwind CSS, Pinia, Vite |
| Backend | 8× Lambda (Python 3.11, x86_64), SharedLayer |
| AI/OCR | Textract + Bedrock (Amazon Nova Pro) |
| Sprachausgabe | Amazon Polly (Text-to-Speech, Standard-Engine) |
| Auth | Cognito (OAuth2, teachers-Gruppe, AdminOnly) |
| DB | DynamoDB (On-Demand), SSM Parameter Store |
| IaC | AWS SAM, CloudFormation |
| Domain | vocab.gym.t3r.de (CloudFront + Route 53 + ACM) |

## Projektstruktur

```
vocabgym/
├── frontend/                 # Vue 3 SPA
│   ├── src/
│   │   ├── components/       # UI-Komponenten (practice/, review/, upload/, ...)
│   │   ├── views/            # Seiten (Dashboard, Practice, League, Help, ...)
│   │   ├── stores/           # Pinia Stores (auth, vocab, practice)
│   │   ├── composables/      # useAuth, useUpload, usePractice
│   │   ├── services/         # API client, Cognito, TTS (Polly)
│   │   └── utils/            # fuzzyMatch, languages, validators
│   └── package.json
├── backend/                  # AWS SAM
│   ├── template.yaml         # CloudFormation (alle Ressourcen)
│   ├── functions/
│   │   ├── upload_handler/       # S3 Presigned URLs
│   │   ├── extraction_handler/   # Textract + Bedrock Pipeline
│   │   ├── vocab_crud_handler/   # CRUD für Vokabelsets
│   │   ├── practice_handler/     # Übungen + Smart Repetition
│   │   ├── progress_handler/     # Fortschrittsstatistiken
│   │   ├── league_handler/       # Liga, Profil & Einladungen (admin-create-user)
│   │   ├── goal_handler/         # Lernziele + Deadline-Tracking
│   │   └── polly_handler/        # Aussprache (Polly TTS)
│   └── layers/shared/           # Gemeinsame Utilities
├── scripts/                  # Migrationsskripte
├── docs/                     # Architektur-Dokumentation
├── deploy.sh                 # Deployment (dev/prod)
└── .kiro/steering/           # Projekt-Spezifikationen
```

## Setup

### Voraussetzungen

- Node.js 18+
- Python 3.11+
- AWS CLI + AWS SAM CLI
- Docker (für `sam build --use-container`)

### Frontend (Entwicklung)

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

### Backend (lokal)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
sam local start-api  # http://localhost:3000
```

### Deployment

```bash
# Einfach:
./deploy.sh dev

# Mit Custom Domain (optional):
cat > backend/.env.deploy <<EOF
CERTIFICATE_ARN=arn:aws:acm:us-east-1:...:certificate/xxx
HOSTED_ZONE_ID=Z0XXXXXXXXX
EOF
./deploy.sh dev
```

`deploy.sh` führt aus: `sam build` → `sam deploy` → Stack-Outputs lesen → Frontend bauen → S3 sync → CloudFront invalidieren.

### CI/CD (GitHub Actions)

| Trigger | Workflow | Aktion |
|---------|----------|--------|
| Pull Request → `main` | `test.yml` | Tests ausführen (mandatory) |
| Push → `main` | `deploy-dev.yml` | Tests + Deploy nach dev |
| GitHub Release | `deploy-prod.yml` | Tests + Deploy nach prod |

Die Release-Version (Tag) wird im Dashboard unten angezeigt.

**GitHub Setup:**

1. Environments `dev` und `prod` in Repository Settings anlegen
2. Secrets pro Environment setzen:
   - `AWS_DEPLOY_ROLE_ARN` — IAM Role ARN für OIDC (GitHub → AWS)
   - `CERTIFICATE_ARN` — ACM Zertifikat
   - `HOSTED_ZONE_ID` — Route 53 Zone
3. Branch Protection für `main`:
   - ✅ Require pull request before merging
   - ✅ Require status checks: "Backend Tests", "Frontend Tests"

**Prod-Release erstellen:**
```bash
git tag v1.0.0
git push origin v1.0.0
# Dann auf GitHub: Releases → Create release from tag
```

### Umgebungen

| Stage | Domain | Stack |
|-------|--------|-------|
| `dev` | dev.vocab.gym.t3r.de | vocabtrainer-dev |
| `prod` | vocab.gym.t3r.de | vocabtrainer-prod |

## LLM-Prompts anpassen

Die Extraktions-Prompts liegen im SSM Parameter Store und können ohne Deploy geändert werden:

```bash
aws ssm put-parameter \
  --name /vocabtrainer/dev/prompts/extraction \
  --value "$(cat new_prompt.txt)" \
  --overwrite
```

Platzhalter: `$lang_name_de`, `$raw_text` (Extraction) / `$lang_name`, `$pairs_text` (Verification)

## Nutzerrollen

| Rolle | Zugang | UI-Sprache |
|-------|--------|------------|
| **Schüler** | Einladung per E-Mail durch Lehrer | Du-Form |
| **Lehrer** | Cognito `teachers`-Gruppe | Sie-Form |

Lehrer können:
- Ligen erstellen und verwalten
- Schüler per E-Mail einladen (Cognito admin-create-user)
- Vokabelsets zuweisen
- Fortschritt und Leaderboard einsehen

## Lizenz

Dieses Projekt ist lizenziert unter der [GNU General Public License v3.0 oder später](LICENSE).

Copyright © 2026 Torsten Dreyer

## AI Generated Code

Most of the code has been (and will be in the future) generated by AI using AWS Kiro with the
specs defined in .kiro/steering and lots of manual finetuning during endless vibe sessions.

### Bildnachweise

Das Logo (`frontend/public/logo.svg`) ist urheberrechtlich geschützt: © Alexa Binnewies.
Es ist **nicht** Teil der GPL-Lizenz dieses Projekts; alle Rechte am Logo bleiben vorbehalten.
