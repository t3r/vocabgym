"""Tests for the per-user learning-tips cache (progress_handler)."""

import os
import sys

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'layers', 'shared', 'python'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'functions', 'progress_handler'))

for _k in (
    'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CREDENTIAL_EXPIRATION',
    'AWS_SESSION_EXPIRATION', 'AWS_PROFILE',
):
    os.environ.pop(_k, None)
os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['LEARNING_TIPS_TABLE'] = 'lt-cache'


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


import importlib
import learning_tips_cache as cache
importlib.reload(cache)  # ensure it picks up LEARNING_TIPS_TABLE


def _table(dynamodb):
    dynamodb.create_table(
        TableName='lt-cache',
        KeySchema=[{'AttributeName': 'userId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'userId', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )


CLUSTERS = [
    {'type': 'phonetic', 'words': [{'target': 'un réseau'}, {'target': 'un réseau social'}]},
    {'type': 'genus', 'words': [{'target': 'une nouvelle'}]},
]


def test_fingerprint_stable_and_order_independent():
    a = cache.fingerprint(CLUSTERS)
    # Reordering the words within a cluster must not change the fingerprint.
    reordered = [
        {'type': 'phonetic', 'words': [{'target': 'un réseau social'}, {'target': 'un réseau'}]},
        {'type': 'genus', 'words': [{'target': 'une nouvelle'}]},
    ]
    assert a == cache.fingerprint(reordered)
    # Different mistakes -> different fingerprint.
    changed = [{'type': 'phonetic', 'words': [{'target': 'un bureau'}]}]
    assert a != cache.fingerprint(changed)


@mock_aws
def test_get_or_generate_generates_then_caches():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    _table(dynamodb)
    importlib.reload(cache)

    calls = {'n': 0}
    def gen(clusters):
        calls['n'] += 1
        return [{'title': 'T', 'body': 'B', 'cluster': 'phonetic'}]

    # First call generates.
    tips1 = cache.get_or_generate('u1', CLUSTERS, gen)
    assert tips1 and calls['n'] == 1
    # Second call with same clusters -> served from cache, no regen.
    tips2 = cache.get_or_generate('u1', CLUSTERS, gen)
    assert tips2 == tips1 and calls['n'] == 1


@mock_aws
def test_get_or_generate_regenerates_on_fingerprint_change():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    _table(dynamodb)
    importlib.reload(cache)

    calls = {'n': 0}
    def gen(clusters):
        calls['n'] += 1
        return [{'title': f'T{calls["n"]}', 'body': 'B'}]

    cache.get_or_generate('u1', CLUSTERS, gen)
    # Different clusters -> different fingerprint -> regenerate.
    other = [{'type': 'genus', 'words': [{'target': 'un smartphone'}]}]
    cache.get_or_generate('u1', other, gen)
    assert calls['n'] == 2


@mock_aws
def test_empty_clusters_no_generate():
    dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
    _table(dynamodb)
    importlib.reload(cache)
    called = {'n': 0}
    cache.get_or_generate('u1', [], lambda c: called.__setitem__('n', called['n'] + 1) or [])
    assert cache.get_or_generate('u1', [], lambda c: []) == []
    assert called['n'] == 0
