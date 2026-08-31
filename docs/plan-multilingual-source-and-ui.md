# Plan: Beliebige Quellsprache, mehrsprachige UI & globale Zeitzonen (POST-PAID)

> **Status:** Geplant für **nach** dem Paid-Launch. Tasks 1, 2, 6 sind additiv/
> migrationsfrei und werden **jetzt schon** umgesetzt (hinter Default `de`).
> Tasks 3–5, 7, 8–11 ändern Verhalten und bleiben bis zum Launch hinter einem
> Feature-Gate inaktiv.
>
> **➡️ Beim Start der Paid-Umsetzung an diesen Plan erinnern.**

## Getroffene Entscheidungen

- **1=a** Nur lateinschriftliche Sprachen (Fuzzy-Matching/Akzent-Logik bleibt nutzbar).
- **2=a** Kuratierte Quell→Ziel-Paare (jedes Paar getestet: Prompt, Polly-Voice, Prüfregeln, Artikel/Genus).
- **3=a** UI-Sprache unabhängig vom Lernpaar wählbar, pro Nutzer persistiert (Default aus Browser).
- **4=a** Anrede-Register (du/Sie, tu/vous, tú/usted) pro Sprache wo natürlich, sonst neutral (en).
- **5=a** Zeitzone pro Nutzer gespeichert (Default aus Browser beim ersten Login), serverseitig verlässlich.
- Keine Migration, die bestehende Daten (Deutsch-Sets, Fortschritte, Goals, Ligen) bricht.

## Befunde aus dem Code (Deutsch-Annahmen)

- `backend/layers/shared/python/lib/languages.py` + `frontend/src/utils/languages.js`:
  festes `SOURCE_LANGUAGE = Deutsch`, `SUPPORTED_LANGUAGES` nur Zielsprachen.
- Datenmodell halb vorbereitet: VocabItems nutzen `source`/`target`; Richtungen
  `source-target`/`target-source`. Nur Legacy `de-fr`/`fr-de` + UI-Labels sind
  deutsch-fest. VocabSets haben `targetLanguage`, aber **kein** `sourceLanguage`.
- `extraction_handler`: Default-Prompt + Substitution nennen „Deutsch ↔ {lang}";
  Prompts liegen in SSM (ohne Deploy änderbar).
- `practice_handler/answer_checker.py`: entfernt Diakritika (é→e, ü→u) und strippt
  Artikel via `get_all_articles(target)` → nutzt implizit die deutsche
  Quell-Artikelliste. Für nicht-lateinische Schriften destruktiv (out of scope).
- UI: kein `vue-i18n`, alle Strings inline deutsch. Du/Sie hängt an `authStore.role`.
- Zeit: `goal_handler` (`_today_local`) und `league_handler` (Weekly-Reset, UTC+2-
  Näherung) rechnen `Europe/Berlin`.

## Task-Breakdown

### Jetzt umsetzbar (additiv, migrationsfrei) — UMGESETZT

- **Task 1 — Sprach-Registry & Paar-Matrix (geteilt BE+FE).**
  `LANGUAGES[code] = {code, name, endonym, articles, articleGenders, register,
  stripsDiacritics, pollyVoices, latinScript}` plus
  `SUPPORTED_PAIRS = [{source, target, promptKey}]`. Deutsch ist normaler
  Eintrag; `de` bleibt Default-Quelle. Helper `get_pair`, `is_pair_supported`,
  `get_articles`. Rückwärtskompatibel: `get_language`, `get_all_articles`,
  `get_article_genders`, `SOURCE_LANGUAGE`, `SUPPORTED_LANGUAGES`,
  `DEFAULT_TARGET_LANGUAGE` bleiben (als Ableitungen aus dem Registry).
  Für JETZT nur Paare `de→fr`, `de→en`, `de→es`, `de→it`.

- **Task 2 — `sourceLanguage` im Datenmodell (additiv).**
  VocabSet bekommt `sourceLanguage`. Lesen defaultet auf `de` → Altbestand liest
  sich als Deutsch. Validation akzeptiert das Feld; ungültiges Paar → 400.
  Fehlendes Feld ist erlaubt (Default de).

- **Task 6 — Nutzer-Präferenzen `uiLanguage` + `timezone` (Backend).**
  `Users.preferences` um `uiLanguage` + `timezone` erweitern.
  `GET/PUT /users/profile` gibt sie zurück/akzeptiert sie (validieren:
  uiLanguage ∈ Registry, timezone ∈ IANA via `zoneinfo`). Defaults
  `uiLanguage='de'`, `timezone='Europe/Berlin'`. `tzdata` in league_handler
  requirements gepinnt.

### Nach Paid-Launch (verhaltensändernd, hinter Feature-Gate) — NICHT umgesetzt

- **Task 3 — answer_checker sprach-parametrisiert.**
  `check_answer(user, correct, source_language, target_language)`. Diakritika-
  Strippen nur wenn `stripsDiacritics` der Sprache true. Aufrufer übergeben
  Set-Sprachen.

- **Task 4 — Extraction pro Sprachpaar (SSM-Prompts).**
  Key-Schema `…/prompts/extraction/{source}-{target}` mit Fallback auf
  generischen Prompt (`{source_name}`/`{target_name}`). Default-Prompt
  neutralisieren. `verify_with_bedrock` analog.

- **Task 5 — Polly-Voices pro Sprache (beidseitig).**
  `polly_handler`/`tts.js` lösen Voices für jede Registry-Sprache auf, nicht nur
  Zielsprachen.

- **Task 7 — Serverseitige Tageslogik auf Nutzer-TZ.**
  `goal_handler` (`_today_local`) + `league_handler` (Weekly-Reset,
  Streak-Tageswechsel) nutzen gespeicherte Nutzer-TZ. Shared-Helper
  `user_today(user)`. `tzdata` in requirements.

- **Task 8 — vue-i18n einführen + Locale-Extraktion (ohne Sichtänderung).**
  `de.json` als Basis aus bestehenden Strings (Register-Varianten für du/Sie über
  rollenabhängige Keys). Locale-Init aus `prefs.uiLanguage` → Browser → `de`.

- **Task 9 — Zweite UI-Locale + Register + Sprachumschalter (sichtbar).**
  `en.json` (neutral). Umschalter im Profil-Editor, persistiert via
  `PUT /users/profile`. Du/Sie-Logik generalisiert (role + Locale-Register).

- **Task 10 — Frontend-Sprachpaar-Auswahl + End-to-End.**
  Upload: Quellsprach-Auswahl (nur Paare aus Matrix). Review/Practice/Detail
  nutzen `sourceLanguage` statt „Deutsch" in Labels/Platzhaltern. Legacy
  `de-fr`/`fr-de` bleibt akzeptiert; neue Sets nur `source-target`/`target-source`.

- **Task 11 — Doku, Steering & Feature-Gate.**
  Steering-Docs aktualisieren; Feature hinter Flag/Plan-Gate; kuratierte Paarliste
  dokumentieren; README-Sprachliste ergänzen.
