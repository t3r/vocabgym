"""Migrate existing vocab data to multi-language format.

This script:
1. Adds targetLanguage='fr' to all VocabSets that don't have it
2. Renames german→source and french→target in all VocabItems

Usage:
    python3 scripts/migrate_to_multilang.py [--env dev|prod] [--dry-run]
"""

import argparse
import boto3

def migrate_vocab_sets(table_name, dry_run=False):
    """Add targetLanguage='fr' to all sets that don't have it."""
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    table = dynamodb.Table(table_name)

    print(f'Scanning {table_name}...')
    response = table.scan()
    items = response['Items']

    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response['Items'])

    count = 0
    for item in items:
        if 'targetLanguage' not in item:
            if dry_run:
                print(f"  [DRY-RUN] Would set targetLanguage='fr' on set {item['vocabSetId']}")
            else:
                table.update_item(
                    Key={'vocabSetId': item['vocabSetId'], 'userId': item['userId']},
                    UpdateExpression='SET targetLanguage = :lang',
                    ExpressionAttributeValues={':lang': 'fr'}
                )
            count += 1

    print(f'{"Would update" if dry_run else "Updated"} {count} vocab sets with targetLanguage=fr')
    return count


def migrate_vocab_items(table_name, dry_run=False):
    """Rename german→source, french→target in all items."""
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    table = dynamodb.Table(table_name)

    print(f'Scanning {table_name}...')
    response = table.scan()
    items = response['Items']

    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response['Items'])

    count = 0
    for item in items:
        if 'german' in item and 'source' not in item:
            if dry_run:
                print(f"  [DRY-RUN] Would migrate item {item['itemId']} in set {item['vocabSetId']}")
                print(f"    german='{item.get('german', '')}' → source")
                print(f"    french='{item.get('french', '')}' → target")
            else:
                table.update_item(
                    Key={'vocabSetId': item['vocabSetId'], 'itemId': item['itemId']},
                    UpdateExpression='SET #src = :src, #tgt = :tgt REMOVE #ger, #fre',
                    ExpressionAttributeNames={
                        '#src': 'source',
                        '#tgt': 'target',
                        '#ger': 'german',
                        '#fre': 'french',
                    },
                    ExpressionAttributeValues={
                        ':src': item.get('german', ''),
                        ':tgt': item.get('french', ''),
                    }
                )
            count += 1

    print(f'{"Would migrate" if dry_run else "Migrated"} {count} vocab items from german/french to source/target')
    return count


def main():
    parser = argparse.ArgumentParser(description='Migrate VocabGym data to multi-language format')
    parser.add_argument('--env', choices=['dev', 'prod'], default='dev', help='Environment (default: dev)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    args = parser.parse_args()

    vocabsets_table = f'vocabtrainer-vocabsets-{args.env}'
    vocabitems_table = f'vocabtrainer-vocabitems-{args.env}'

    print(f'=== VocabGym Multi-Language Migration ===')
    print(f'Environment: {args.env}')
    print(f'Dry run: {args.dry_run}')
    print()

    sets_count = migrate_vocab_sets(vocabsets_table, dry_run=args.dry_run)
    print()
    items_count = migrate_vocab_items(vocabitems_table, dry_run=args.dry_run)

    print()
    print(f'=== Summary ===')
    print(f'VocabSets updated: {sets_count}')
    print(f'VocabItems migrated: {items_count}')

    if args.dry_run:
        print()
        print('This was a dry run. Run without --dry-run to apply changes.')


if __name__ == '__main__':
    main()
