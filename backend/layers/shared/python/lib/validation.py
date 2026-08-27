"""Input validation helpers for VocabTrainer."""

import logging
import re

logger = logging.getLogger(__name__)

# Allowed image MIME types
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png'}

# Maximum file size in bytes (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Maximum text field lengths
MAX_TITLE_LENGTH = 100
MAX_VOCAB_WORD_LENGTH = 200
MAX_NOTES_LENGTH = 500
MAX_CHAPTER_LENGTH = 50
MAX_TOPIC_LENGTH = 100


def validate_file_upload(file_name, content_type):
    """Validate file upload parameters.

    Args:
        file_name: Original file name
        content_type: MIME type of the file

    Returns:
        tuple: (is_valid, error_message)
    """
    if not file_name:
        return False, "File name is required"

    if not content_type:
        return False, "Content type is required"

    if content_type not in ALLOWED_IMAGE_TYPES:
        return False, f"Unsupported file type: {content_type}. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}"

    # Validate file extension
    valid_extensions = {'.jpg', '.jpeg', '.png'}
    ext = '.' + file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''
    if ext not in valid_extensions:
        return False, f"Invalid file extension. Allowed: {', '.join(valid_extensions)}"

    # Sanitize file name (prevent path traversal)
    if '..' in file_name or '/' in file_name or '\\' in file_name:
        return False, "Invalid characters in file name"

    return True, None


def validate_vocab_set_data(data):
    """Validate vocabulary set data for create/update.

    Args:
        data: Dictionary with vocab set fields

    Returns:
        tuple: (is_valid, error_message)
    """
    if not data:
        return False, "Request body is required"

    title = data.get('title', '')
    if title and len(title) > MAX_TITLE_LENGTH:
        return False, f"Title must be {MAX_TITLE_LENGTH} characters or fewer"

    metadata = data.get('metadata', {})
    if metadata:
        chapter = metadata.get('chapter', '')
        if chapter and len(chapter) > MAX_CHAPTER_LENGTH:
            return False, f"Chapter must be {MAX_CHAPTER_LENGTH} characters or fewer"

        topic = metadata.get('topic', '')
        if topic and len(topic) > MAX_TOPIC_LENGTH:
            return False, f"Topic must be {MAX_TOPIC_LENGTH} characters or fewer"

        page_number = metadata.get('pageNumber')
        if page_number is not None:
            try:
                page_num = int(page_number)
                if page_num < 1 or page_num > 9999:
                    return False, "Page number must be between 1 and 9999"
            except (ValueError, TypeError):
                return False, "Page number must be a positive integer"

    return True, None


def validate_vocab_items(items):
    """Validate a list of vocabulary items.

    Args:
        items: List of vocabulary item dicts with 'source'/'target' keys
               (also accepts legacy 'german'/'french' keys for backwards compat)

    Returns:
        tuple: (is_valid, error_message)
    """
    if not items:
        return False, "At least one vocabulary item is required"

    if not isinstance(items, list):
        return False, "Items must be a list"

    if len(items) > 500:
        return False, "Maximum 500 items per vocabulary set"

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            return False, f"Item {i+1} must be an object"

        # Accept both source/target (new) and german/french (legacy)
        source = item.get('source', item.get('german', '')).strip()
        target = item.get('target', item.get('french', '')).strip()

        if not source:
            return False, f"Item {i+1}: Source word is required"

        if not target:
            return False, f"Item {i+1}: Target word is required"

        if len(source) > MAX_VOCAB_WORD_LENGTH:
            return False, f"Item {i+1}: Source word exceeds maximum length of {MAX_VOCAB_WORD_LENGTH}"

        if len(target) > MAX_VOCAB_WORD_LENGTH:
            return False, f"Item {i+1}: Target word exceeds maximum length of {MAX_VOCAB_WORD_LENGTH}"

    return True, None


def validate_practice_options(data):
    """Validate practice session start options.

    Args:
        data: Dictionary with practice options

    Returns:
        tuple: (is_valid, error_message)
    """
    if not data:
        return False, "Request body is required"

    vocab_set_id = data.get('vocabSetId')
    if not vocab_set_id:
        return False, "vocabSetId is required"

    direction = data.get('direction', 'de-fr')
    if direction not in ('de-fr', 'fr-de', 'source-target', 'target-source'):
        return False, "Direction must be 'de-fr', 'fr-de', 'source-target', or 'target-source'"

    question_count = data.get('questionCount')
    if question_count is not None:
        try:
            count = int(question_count)
            if count < 1 or count > 500:
                return False, "questionCount must be between 1 and 500"
        except (ValueError, TypeError):
            return False, "questionCount must be a positive integer"

    return True, None


def validate_uuid(value, field_name="ID"):
    """Validate that a value looks like a UUID.

    Args:
        value: String to validate
        field_name: Name of the field for error messages

    Returns:
        tuple: (is_valid, error_message)
    """
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    if not value or not uuid_pattern.match(value):
        return False, f"Invalid {field_name} format"
    return True, None
