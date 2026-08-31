# Rechtstexte (Datenschutz & Impressum)

Die echten Rechtstexte enthalten personenbezogene Daten (Name, Anschrift,
E-Mail des Verantwortlichen) und werden **nicht** in git eingecheckt. Sie
liegen in S3 und werden über dieselbe CloudFront-Distribution ausgeliefert;
die Views `PrivacyView.vue` / `ImpressumView.vue` laden sie zur Laufzeit von
`/legal/privacy.de.html` bzw. `/legal/impressum.de.html`.

In git sind nur die `*.example.html`-Vorlagen (mit Platzhaltern).

## Einmalige Einrichtung pro Umgebung

1. Werte in einer `.env` hinterlegen und die echten Dateien generieren
   (echte `*.html` sind git-ignored, `legal/.env` ebenfalls):

   ```bash
   cp legal/.env.example legal/.env
   # legal/.env ausfüllen (Name, Anschrift, E-Mail, ...)
   python3 scripts/render_legal.py            # erzeugt legal/privacy.de.html + impressum.de.html
   # optional vorab prüfen, ohne zu schreiben:
   python3 scripts/render_legal.py --check
   ```

   Der Generator ersetzt die `[Platzhalter]` aus den `*.example.html`-Vorlagen
   mit den Werten aus `legal/.env`, entfernt den Entwickler-Kommentarblock und
   bricht ab, falls ein Platzhalter unbefüllt bleibt (kein versehentliches
   Veröffentlichen von Vorlagentext). Ein leeres `LEGAL_PHONE` lässt die
   Telefonzeile entfallen; ein leeres `LEGAL_PRIVACY_DATE` setzt das heutige
   Datum.

2. Frontend-Bucketnamen aus dem Stack holen (dev oder prod):

   ```bash
   BUCKET=$(aws cloudformation describe-stacks \
     --stack-name vocabtrainer-dev --region eu-central-1 \
     --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
     --output text)
   ```

3. Dateien mit korrektem Content-Type nach S3 laden (Prefix `legal/`):

   ```bash
   aws s3 cp legal/privacy.de.html   "s3://$BUCKET/legal/privacy.de.html"   --content-type "text/html; charset=utf-8" --region eu-central-1
   aws s3 cp legal/impressum.de.html "s3://$BUCKET/legal/impressum.de.html" --content-type "text/html; charset=utf-8" --region eu-central-1
   ```

4. CloudFront-Cache für die Rechtstexte invalidieren:

   ```bash
   DIST=$(aws cloudformation describe-stacks \
     --stack-name vocabtrainer-dev --region eu-central-1 \
     --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
     --output text)
   aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/legal/*" --region eu-central-1
   ```

## Wichtig

- `deploy.sh` synchronisiert das Frontend mit `--delete`, schließt aber
  `legal/*` aus (`--exclude "legal/*"`). Deine hochgeladenen Rechtstexte
  werden dadurch bei einem Deploy **nicht** gelöscht.
- Es wird nur der HTML-Rumpf ausgeliefert (kein `<html>/<head>/<body>`),
  da der Inhalt in die bestehende App-Seite eingebettet wird.
- Zum Aktualisieren der Texte genügt ein erneuter `aws s3 cp` + Invalidation —
  kein Code-Deploy nötig.
