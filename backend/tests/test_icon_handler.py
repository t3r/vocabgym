"""Tests for the event-driven icon_handler (robohash identicons).

Covers:
- image key -> icon key mapping (one icon per page)
- deterministic seeding from the full key
- rendering both styles to S3 (moto)
- idempotency (skip when icon already exists)
- loop/scope guard (never processes identicons/ writes or foreign prefixes)
"""

import importlib.util
import io
import os
import sys

import boto3
import pytest
from moto import mock_aws

# Remove any real (possibly expired) AWS session credentials from the env so
# botocore does not try to refresh them; then set deterministic fake creds so
# moto intercepts all calls. Without this, an expired AWS_SESSION_TOKEN in the
# developer/CI environment makes boto raise before moto can mock the call.
for _k in (
    'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CREDENTIAL_EXPIRATION',
    'AWS_SESSION_EXPIRATION', 'AWS_PROFILE',
):
    os.environ.pop(_k, None)
os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['REGION'] = 'eu-central-1'

_ICON_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'functions', 'icon_handler', 'app.py'
)

# Are the heavy render deps present? Skip only the render-dependent asserts if not.
try:
    import robohash  # noqa: F401
    import PIL  # noqa: F401
    _HAS_RENDER_DEPS = True
except Exception:
    _HAS_RENDER_DEPS = False


def _load_icon_app(env):
    for k, v in env.items():
        os.environ[k] = v
    spec = importlib.util.spec_from_file_location('icon_app_under_test', _ICON_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _clean_aws_creds():
    """Ensure no real/expired session credentials leak into moto tests.

    conftest snapshots and restores os.environ around each test, so the
    module-level cleanup is not enough — re-apply it before every test.
    """
    for k in (
        'AWS_SESSION_TOKEN', 'AWS_SECURITY_TOKEN', 'AWS_CREDENTIAL_EXPIRATION',
        'AWS_SESSION_EXPIRATION', 'AWS_PROFILE',
    ):
        os.environ.pop(k, None)
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
    yield


_ENV = {
    'IMAGES_BUCKET': 'test-images-bucket',
    'REGION': 'eu-central-1',
}


# ------------------------- pure key logic (no AWS/deps) -------------------------

def test_icon_key_mapping_strips_prefix_and_original_suffix():
    app = _load_icon_app(_ENV)
    src = 'images/user-1/set-abc/1693400000-original.jpg'
    assert app._icon_key(src, 'set1') == 'identicons/user-1/set-abc/1693400000-set1.png'
    assert app._icon_key(src, 'set4') == 'identicons/user-1/set-abc/1693400000-set4.png'


def test_icon_key_handles_png_original():
    app = _load_icon_app(_ENV)
    src = 'images/u/v/999-original.png'
    assert app._icon_key(src, 'set1') == 'identicons/u/v/999-set1.png'


def test_seed_is_deterministic_and_key_specific():
    app = _load_icon_app(_ENV)
    k1 = 'images/u/v/1-original.jpg'
    k2 = 'images/u/v/2-original.jpg'  # different page, same set
    assert app._seed_for_key(k1) == app._seed_for_key(k1)  # deterministic
    assert app._seed_for_key(k1) != app._seed_for_key(k2)  # per-page unique


def test_extract_image_keys_eventbridge_and_urldecoding():
    app = _load_icon_app(_ENV)
    event = {
        'detail': {
            'bucket': {'name': 'test-images-bucket'},
            'object': {'key': 'images/u/v/1693-original.jpg'},
        }
    }
    assert app._extract_image_keys(event) == ['images/u/v/1693-original.jpg']

    # URL-encoded key (spaces -> '+')
    event2 = {'detail': {'object': {'key': 'images/u/v/my+file-original.jpg'}}}
    assert app._extract_image_keys(event2) == ['images/u/v/my file-original.jpg']


def test_extract_image_keys_s3_native_fallback():
    app = _load_icon_app(_ENV)
    event = {'Records': [{'s3': {'object': {'key': 'images/u/v/1-original.jpg'}}}]}
    assert app._extract_image_keys(event) == ['images/u/v/1-original.jpg']


# ------------------------- loop / scope guard -------------------------

@mock_aws
def test_ignores_identicon_prefix_no_loop():
    """A write under identicons/ must never trigger rendering (infinite-loop guard)."""
    boto3.client('s3', region_name='eu-central-1').create_bucket(
        Bucket='test-images-bucket',
        CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'},
    )
    app = _load_icon_app(_ENV)
    result = app._process_image_key('identicons/u/v/1-set1.png')
    assert result == []


@mock_aws
def test_ignores_foreign_prefix():
    boto3.client('s3', region_name='eu-central-1').create_bucket(
        Bucket='test-images-bucket',
        CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'},
    )
    app = _load_icon_app(_ENV)
    assert app._process_image_key('tts/u/whatever.mp3') == []


# ------------------------- rendering (needs robohash+Pillow) -------------------------

@pytest.mark.skipif(not _HAS_RENDER_DEPS, reason='robohash/Pillow not installed')
@mock_aws
def test_renders_both_styles_to_s3():
    s3 = boto3.client('s3', region_name='eu-central-1')
    s3.create_bucket(
        Bucket='test-images-bucket',
        CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'},
    )
    app = _load_icon_app(_ENV)

    src = 'images/user-1/set-abc/1693400000-original.jpg'
    written = app._process_image_key(src)

    assert set(written) == {
        'identicons/user-1/set-abc/1693400000-set1.png',
        'identicons/user-1/set-abc/1693400000-set4.png',
    }
    # Both objects really exist and are non-trivial PNGs
    for key in written:
        obj = s3.get_object(Bucket='test-images-bucket', Key=key)
        body = obj['Body'].read()
        assert body[:8] == b'\x89PNG\r\n\x1a\n'  # PNG magic
        assert len(body) > 1000


@pytest.mark.skipif(not _HAS_RENDER_DEPS, reason='robohash/Pillow not installed')
@mock_aws
def test_idempotent_skips_existing():
    s3 = boto3.client('s3', region_name='eu-central-1')
    s3.create_bucket(
        Bucket='test-images-bucket',
        CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'},
    )
    app = _load_icon_app(_ENV)
    src = 'images/u/v/1-original.jpg'

    app._process_image_key(src)
    # Overwrite one icon with a sentinel; a re-run must NOT overwrite it (skipped).
    sentinel_key = 'identicons/u/v/1-set1.png'
    s3.put_object(Bucket='test-images-bucket', Key=sentinel_key, Body=b'SENTINEL')

    app._process_image_key(src)  # second run
    body = s3.get_object(Bucket='test-images-bucket', Key=sentinel_key)['Body'].read()
    assert body == b'SENTINEL'  # untouched -> idempotent


@pytest.mark.skipif(not _HAS_RENDER_DEPS, reason='robohash/Pillow not installed')
@mock_aws
def test_lambda_handler_end_to_end():
    s3 = boto3.client('s3', region_name='eu-central-1')
    s3.create_bucket(
        Bucket='test-images-bucket',
        CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'},
    )
    app = _load_icon_app(_ENV)
    event = {
        'detail': {
            'bucket': {'name': 'test-images-bucket'},
            'object': {'key': 'images/u/v/42-original.jpg'},
        }
    }
    result = app.lambda_handler(event, None)
    assert len(result['rendered']) == 2
