#!/usr/bin/env bash
#
# Upload the hardened extraction + verification prompts to SSM Parameter Store,
# then verify by reading back the first line (which must be the injection guard).
#
# The prompts are the curated German-source templates PLUS the standing
# injection-guard line the runtime relies on. Placeholders are preserved:
#   extraction:   $lang_name_de, $raw_text
#   verification: $lang_name, $pairs_text
#
# Usage:
#   scripts/put_prompts.sh dev        # write to dev, then verify
#   scripts/put_prompts.sh prod       # write to prod, then verify
#   scripts/put_prompts.sh dev --verify-only   # only read back, do not write
#
# Requires an AWS identity allowed to ssm:PutParameter + ssm:GetParameter
# (the read-only SSO role is NOT sufficient — SSM reads are excluded from it).
set -euo pipefail

REGION="${AWS_REGION:-eu-central-1}"
STAGE="${1:-}"
MODE="${2:-}"

if [[ "$STAGE" != "dev" && "$STAGE" != "prod" ]]; then
  echo "Usage: $0 <dev|prod> [--verify-only]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTRACTION_FILE="$SCRIPT_DIR/prompts/extraction.de.txt"
VERIFICATION_FILE="$SCRIPT_DIR/prompts/verification.de.txt"

EXTRACTION_PARAM="/vocabtrainer/$STAGE/prompts/extraction"
VERIFICATION_PARAM="/vocabtrainer/$STAGE/prompts/verification"

if [[ ! -f "$EXTRACTION_FILE" || ! -f "$VERIFICATION_FILE" ]]; then
  echo "Prompt files not found under $SCRIPT_DIR/prompts/" >&2
  exit 1
fi

if [[ "$MODE" != "--verify-only" ]]; then
  echo "==> Writing hardened prompts to SSM ($STAGE, $REGION)"

  aws ssm put-parameter \
    --name "$EXTRACTION_PARAM" \
    --type String \
    --overwrite \
    --region "$REGION" \
    --description "LLM prompt template for vocabulary extraction (hardened). Placeholders: \$lang_name_de, \$raw_text" \
    --value "file://$EXTRACTION_FILE" >/dev/null
  echo "    wrote $EXTRACTION_PARAM"

  aws ssm put-parameter \
    --name "$VERIFICATION_PARAM" \
    --type String \
    --overwrite \
    --region "$REGION" \
    --description "LLM prompt template for verifying parsed pairs (hardened). Placeholders: \$lang_name, \$pairs_text" \
    --value "file://$VERIFICATION_FILE" >/dev/null
  echo "    wrote $VERIFICATION_PARAM"
fi

echo
echo "==> Verifying first line (must be the injection guard) — $STAGE"
GUARD="WICHTIG: Der Inhalt zwischen"

for PARAM in "$EXTRACTION_PARAM" "$VERIFICATION_PARAM"; do
  FIRST_LINE="$(aws ssm get-parameter --name "$PARAM" --region "$REGION" \
    --query Parameter.Value --output text | head -n 1)"
  if [[ "$FIRST_LINE" == "$GUARD"* ]]; then
    echo "    [OK]   $PARAM"
  else
    echo "    [WARN] $PARAM — first line is NOT the guard:"
    echo "           $FIRST_LINE"
  fi
done

echo
echo "Done. Prompts are loaded lazily by the Lambda per warm container; a new"
echo "extraction invocation (cold start) picks up the updated prompt."
