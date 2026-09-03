"""Tests for duplicate-word prevention in extraction (store_vocab_items).

Regression: multi-page uploads produced two vocab items sharing one meaning
(e.g. 'une tablette' from 'ein Tablet-Computer' AND 'ein Tablet(-Computer)'),
which then reappeared in practice even after being mastered. store_vocab_items
must store each normalized target only once per set — across the batch AND
against items already stored from earlier pages.
"""

import importlib.util
import os
import sys

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'shared', 'python'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'functions', 'extraction_handler'))

for _k in (
    'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CREDENTIAL_EXPIRATION',
    'AWS_SESSION_EXPIRATION', 'AWS_PROFILE',
):
    os.environ.pop(_k, None)
os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'

_APP_PATH = os.path.join(os.path.dirname(__file__), '..', 'functions', 'extraction_handler', 'app.py')

_ENV = {
    'IMAGES_BUCKET': 'dd-images',
    'VOCABSETS_TABLE': 'dd-vocabsets',
    'VOCABITEMS_TABLE': 'dd-vocabitems',
    'EXTRACTION_USAGE_TABLE': 'dd-usage',
    'REGION': 'eu-central-1',
}


@pytest.fixture(autouse=True)
def _clean_creds():
    for k in (
        'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CREDENTIAL_EXPIRATION',
        'AWS_SESSION_EXPIRATION', 'AWS_PROFILE',
    ):
        os.environ.pop(k, None)
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
    yield


def _load():
    for k, v in _ENV.items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location('extraction_dedup_app', _APP_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules['extraction_dedup_app'] = module
    spec.loader.exec_module(module)
    return module


def _items_table(ddb):
    ddb.create_table(
        TableName='dd-vocabitems',
        KeySchema=[
            {'AttributeName': 'vocabSetId', 'KeyType': 'HASH'},
            {'AttributeName': 'itemId', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'vocabSetId', 'AttributeType': 'S'},
            {'AttributeName': 'itemId', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )


def _targets(ddb, vsid):
    resp = ddb.Table('dd-vocabitems').query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('vocabSetId').eq(vsid)
    )
    return sorted(i.get('target', '') for i in resp.get('Items', []))


class TestNormalizeDedupKey:
    def test_normalizes_punctuation_case_and_brackets(self):
        app = _load()
        # These are the real-world variants that must collapse to one key.
        assert app._normalize_dedup_key('une tablette') == app._normalize_dedup_key('Une Tablette')
        assert app._normalize_dedup_key('une application') == \
            app._normalize_dedup_key('une application (ein Programm)')
        assert app._normalize_dedup_key('télécharger qc.') == app._normalize_dedup_key('télécharger qc')

    def test_distinct_words_stay_distinct(self):
        app = _load()
        assert app._normalize_dedup_key('un écran') != app._normalize_dedup_key('un smartphone')

    def test_empty(self):
        app = _load()
        assert app._normalize_dedup_key('') == ''
        assert app._normalize_dedup_key(None) == ''


@mock_aws
def test_dedupes_within_a_single_batch():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _items_table(ddb)
    app = _load()

    pairs = [
        {'source': 'ein Tablet-Computer', 'target': 'une tablette'},
        {'source': 'ein Tablet(-Computer)', 'target': 'une tablette'},  # dup meaning
        {'source': 'ein Bildschirm', 'target': 'un écran'},
    ]
    stored = app.store_vocab_items('set-1', pairs)
    assert stored == 2  # tablette stored once, écran once
    assert _targets(ddb, 'set-1') == ['un écran', 'une tablette']


@mock_aws
def test_dedupes_against_items_from_earlier_pages():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _items_table(ddb)
    app = _load()

    # Page 1
    app.store_vocab_items('set-1', [{'source': 'ein Smartphone', 'target': 'un smartphone'}])
    # Page 2 repeats the word (different source punctuation) — must be skipped.
    stored = app.store_vocab_items('set-1', [
        {'source': 'ein Smartphone!', 'target': 'un smartphone'},
        {'source': 'eine App', 'target': 'une application'},
    ])
    assert stored == 1  # only the new 'une application'
    assert _targets(ddb, 'set-1') == ['un smartphone', 'une application']


@mock_aws
def test_skips_empty_targets():
    ddb = boto3.resource('dynamodb', region_name='eu-central-1')
    _items_table(ddb)
    app = _load()
    stored = app.store_vocab_items('set-1', [
        {'source': 'nur deutsch', 'target': ''},
        {'source': 'ok', 'target': 'valide'},
    ])
    assert stored == 1
    assert _targets(ddb, 'set-1') == ['valide']
