"""Backfill robohash identicons for vocab sets that were created before the
icon_handler existed.

For every image key stored on a VocabSet (sourceImageKey + imageKeys), this
renders the two identicon styles (set1 robots, set4 cats) and writes them to
the identicons/ prefix — exactly the same keys the icon_handler would produce
on a fresh upload.

Key facts that make this safe and simple:
- The identicon seed is the image KEY (a string), never the image bytes. So we
  do NOT need the original scan to exist — a set whose original was already
  deleted (old 30/90-day lifecycle) still gets its icon, derived purely from the
  key stored in DynamoDB.
- It reuses the real icon_handler rendering functions, so migration output is
  byte-for-byte what the live handler produces (no logic drift).
- Idempotent: existing icons are skipped (head_object), so it is safe to re-run.

Requirements (already in the backend venv):
    pip install robohash==2.0 Pillow

Usage:
    python3 scripts/backfill_identicons.py --env dev [--dry-run]
    python3 scripts/backfill_identicons.py --env prod            # after verifying dev

Requires AWS credentials with dynamodb:Scan on the vocabsets table and
s3:PutObject/HeadObject on the images bucket (identicons/ prefix).
"""

import argparse
import os
import sys

import boto3

# Reuse the real icon_handler logic so migration output matches production 1:1.
_ICON_DIR = os.path.join(
    os.path.dirname(__file__), '..', 'backend', 'functions', 'icon_handler'
)
sys.path.insert(0, _ICON_DIR)

REGION = 'eu-central-1'


def _iter_vocabsets(table):
    """Yield all items from the vocabsets table (handles pagination)."""
    response = table.scan()
    for item in response.get('Items', []):
        yield item
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        for item in response.get('Items', []):
            yield item


def _image_keys_for(vocab_set):
    """Collect all original image keys referenced by a set (deduped, images/ only)."""
    keys = []
    src = vocab_set.get('sourceImageKey')
    if src:
        keys.append(src)
    for k in vocab_set.get('imageKeys', []) or []:
        if k not in keys:
            keys.append(k)
    return [k for k in keys if isinstance(k, str) and k.startswith('images/')]


def main():
    parser = argparse.ArgumentParser(description='Backfill identicons for existing vocab sets')
    parser.add_argument('--env', choices=['dev', 'prod'], default='dev')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be rendered without writing to S3')
    args = parser.parse_args()

    # Import handler logic + set the bucket env it expects.
    account_id = boto3.client('sts', region_name=REGION).get_caller_identity()['Account']
    bucket = f'vocabtrainer-images-{args.env}-{account_id}'
    os.environ['IMAGES_BUCKET'] = bucket
    os.environ.setdefault('ICON_SIZE', '256')

    import app as icon_app  # backend/functions/icon_handler/app.py

    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    vocabsets_table = dynamodb.Table(f'vocabtrainer-vocabsets-{args.env}')

    print('=== VocabGym Identicon Backfill ===')
    print(f'Environment : {args.env}')
    print(f'Bucket      : {bucket}')
    print(f'Dry run     : {args.dry_run}')
    print()

    sets_seen = 0
    keys_seen = 0
    rendered = 0
    skipped = 0

    for vocab_set in _iter_vocabsets(vocabsets_table):
        sets_seen += 1
        for image_key in _image_keys_for(vocab_set):
            keys_seen += 1
            for roboset in icon_app.ICON_SETS:
                icon_key = icon_app._icon_key(image_key, roboset)
                if icon_app._already_rendered(icon_key):
                    skipped += 1
                    continue
                if args.dry_run:
                    print(f'  [DRY-RUN] would render {icon_key}')
                    rendered += 1
                    continue
                seed = icon_app._seed_for_key(image_key)
                png = icon_app._render_identicon(seed, roboset)
                icon_app.s3_client.put_object(
                    Bucket=bucket, Key=icon_key, Body=png, ContentType='image/png'
                )
                print(f'  rendered {icon_key} ({len(png)} bytes)')
                rendered += 1

    print()
    print('=== Summary ===')
    print(f'Vocab sets scanned : {sets_seen}')
    print(f'Image keys found   : {keys_seen}')
    print(f'Icons {"would render" if args.dry_run else "rendered"} : {rendered}')
    print(f'Icons skipped (exist): {skipped}')
    if args.dry_run:
        print()
        print('Dry run only. Re-run without --dry-run to write icons to S3.')


if __name__ == '__main__':
    main()
