"""Textract response parser for extracting vocabulary tables."""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TextractParser:
    """Parse AWS Textract AnalyzeDocument response to extract vocabulary pairs.

    Textract returns a list of Block objects representing different elements
    detected in the document. For tables, the hierarchy is:
    TABLE -> CELL -> WORD

    This parser identifies table structures, extracts cell content,
    and determines German-French column pairs using heuristics.
    """

    def __init__(self, textract_response: dict):
        """Initialize the parser with a Textract response.

        Args:
            textract_response: Raw response from textract.analyze_document()
        """
        self.blocks = textract_response.get('Blocks', [])
        self.block_map = {block['Id']: block for block in self.blocks}

    def extract_vocabulary_pairs(self) -> List[Dict]:
        """Extract vocabulary pairs from all tables in the document.

        Returns:
            List of dicts with keys: source, target, confidence, notes
        """
        tables = self._get_tables()

        if not tables:
            logger.info("No tables found in document, attempting line-based extraction")
            return self._extract_from_lines()

        all_pairs = []
        for table in tables:
            pairs = self._extract_pairs_from_table(table)
            all_pairs.extend(pairs)

        return all_pairs

    def _get_tables(self) -> List[dict]:
        """Get all TABLE blocks from the response."""
        return [block for block in self.blocks if block['BlockType'] == 'TABLE']

    def _get_cells_for_table(self, table_block: dict) -> List[dict]:
        """Get all CELL blocks belonging to a table.

        Args:
            table_block: A TABLE type block

        Returns:
            List of CELL blocks
        """
        cells = []
        relationships = table_block.get('Relationships', [])
        for rel in relationships:
            if rel['Type'] == 'CHILD':
                for child_id in rel['Ids']:
                    child_block = self.block_map.get(child_id)
                    if child_block and child_block['BlockType'] == 'CELL':
                        cells.append(child_block)
        return cells

    def _get_cell_text(self, cell_block: dict) -> str:
        """Extract text content from a cell block.

        Args:
            cell_block: A CELL type block

        Returns:
            String content of the cell
        """
        text_parts = []
        relationships = cell_block.get('Relationships', [])
        for rel in relationships:
            if rel['Type'] == 'CHILD':
                for child_id in rel['Ids']:
                    child_block = self.block_map.get(child_id)
                    if child_block and child_block['BlockType'] == 'WORD':
                        text_parts.append(child_block.get('Text', ''))
        return ' '.join(text_parts).strip()

    def _get_cell_confidence(self, cell_block: dict) -> float:
        """Get average confidence for text in a cell.

        Args:
            cell_block: A CELL type block

        Returns:
            Average confidence score (0-1)
        """
        confidences = []
        relationships = cell_block.get('Relationships', [])
        for rel in relationships:
            if rel['Type'] == 'CHILD':
                for child_id in rel['Ids']:
                    child_block = self.block_map.get(child_id)
                    if child_block and child_block['BlockType'] == 'WORD':
                        confidences.append(child_block.get('Confidence', 0) / 100.0)

        return sum(confidences) / len(confidences) if confidences else 0.0

    def _extract_pairs_from_table(self, table_block: dict) -> List[Dict]:
        """Extract vocabulary pairs from a single table.

        Args:
            table_block: A TABLE type block

        Returns:
            List of vocabulary pair dicts
        """
        cells = self._get_cells_for_table(table_block)

        if not cells:
            return []

        # Organize cells into a grid
        grid = {}  # (row, col) -> cell
        max_row = 0
        max_col = 0

        for cell in cells:
            row = cell.get('RowIndex', 0)
            col = cell.get('ColumnIndex', 0)
            grid[(row, col)] = cell
            max_row = max(max_row, row)
            max_col = max(max_col, col)

        if max_col < 2:
            logger.info("Table has fewer than 2 columns, skipping")
            return []

        # Determine which columns are German and French
        german_col, french_col = self._identify_language_columns(grid, max_row, max_col)

        # Extract pairs from rows (skip header row if detected)
        pairs = []
        start_row = 2 if self._is_header_row(grid, 1, max_col) else 1

        for row in range(start_row, max_row + 1):
            # If table has more than 2 columns, merge all non-target columns as source
            if max_col > 2:
                source_texts = []
                target_texts = []
                for col in range(1, max_col + 1):
                    cell = grid.get((row, col))
                    if not cell:
                        continue
                    text = self._get_cell_text(cell)
                    if not text:
                        continue
                    if col == french_col:
                        target_texts.append(text)
                    else:
                        source_texts.append(text)

                german_text = ' '.join(source_texts).strip()
                french_text = ' '.join(target_texts).strip()
            else:
                german_cell = grid.get((row, german_col))
                french_cell = grid.get((row, french_col))

                if not german_cell or not french_cell:
                    continue

                german_text = self._get_cell_text(german_cell)
                french_text = self._get_cell_text(french_cell)

            # Skip empty rows
            if not german_text or not french_text:
                continue

            # Skip rows that look like headers or instructions
            if self._is_instruction_text(german_text) or self._is_instruction_text(french_text):
                continue

            # Calculate confidence from available cells
            if max_col > 2:
                confidence = 0.85  # Default for merged columns
            else:
                confidence = (
                    self._get_cell_confidence(grid.get((row, german_col), {})) +
                    self._get_cell_confidence(grid.get((row, french_col), {}))
                ) / 2.0

            pairs.append({
                'source': german_text,
                'target': french_text,
                'confidence': round(confidence, 2),
                'notes': '',
            })

        return pairs

    def _identify_language_columns(
        self, grid: dict, max_row: int, max_col: int
    ) -> Tuple[int, int]:
        """Determine which columns contain German and French text.

        Uses heuristics:
        1. Check header row for language indicators
        2. Check for German articles (der, die, das) vs French articles (le, la, les)
        3. Default: assume left=German, right=French

        Args:
            grid: (row, col) -> cell mapping
            max_row: Maximum row index
            max_col: Maximum column index

        Returns:
            Tuple of (german_column_index, french_column_index)
        """
        # Check header row for language indicators
        german_indicators = {'deutsch', 'german', 'de', 'dt.', 'allemand'}
        french_indicators = {'französisch', 'french', 'fr', 'fr.', 'français'}

        for col in range(1, max_col + 1):
            cell = grid.get((1, col))
            if cell:
                text = self._get_cell_text(cell).lower().strip()
                if text in german_indicators:
                    german_col = col
                    french_col = col + 1 if col < max_col else col - 1
                    return german_col, french_col
                elif text in french_indicators:
                    french_col = col
                    german_col = col - 1 if col > 1 else col + 1
                    return german_col, french_col

        # Check content for language markers
        german_articles = {'der', 'die', 'das', 'ein', 'eine'}
        french_articles = {'le', 'la', 'les', 'un', 'une', "l'"}

        col1_german_score = 0
        col2_german_score = 0
        sample_rows = min(5, max_row)

        for row in range(1, sample_rows + 1):
            for col in [1, 2]:
                cell = grid.get((row, col))
                if cell:
                    text = self._get_cell_text(cell).lower()
                    words = text.split()
                    if words:
                        first_word = words[0]
                        if first_word in german_articles:
                            if col == 1:
                                col1_german_score += 1
                            else:
                                col2_german_score += 1
                        elif first_word in french_articles:
                            if col == 1:
                                col2_german_score += 1
                            else:
                                col1_german_score += 1

        if col1_german_score > col2_german_score:
            return 1, 2
        elif col2_german_score > col1_german_score:
            return 2, 1

        # Default: left column = German, right column = French
        return 1, 2

    def _is_header_row(self, grid: dict, row: int, max_col: int) -> bool:
        """Check if a row appears to be a header row.

        Args:
            grid: (row, col) -> cell mapping
            row: Row index to check
            max_col: Maximum column index

        Returns:
            True if row appears to be a header
        """
        header_indicators = {
            'deutsch', 'german', 'de', 'französisch', 'french', 'fr',
            'wort', 'word', 'vocabulaire', 'vokabel', 'mot',
            'allemand', 'français',
        }

        for col in range(1, max_col + 1):
            cell = grid.get((row, col))
            if cell:
                text = self._get_cell_text(cell).lower().strip()
                if text in header_indicators:
                    return True

        return False

    def _is_instruction_text(self, text: str) -> bool:
        """Check if text appears to be an instruction rather than vocabulary.

        Args:
            text: Text to check

        Returns:
            True if text looks like an instruction
        """
        instruction_patterns = [
            'seite', 'page', 'übung', 'exercise',
            'aufgabe', 'kapitel', 'chapter',
        ]
        lower_text = text.lower()
        return any(pattern in lower_text for pattern in instruction_patterns)

    def _extract_from_lines(self) -> List[Dict]:
        """Fallback: Extract vocabulary from LINE blocks when no tables found.

        Looks for patterns like "German word - French word" or tab-separated pairs.

        Returns:
            List of vocabulary pair dicts
        """
        lines = [
            block for block in self.blocks
            if block['BlockType'] == 'LINE'
        ]

        pairs = []
        separators = [' - ', ' – ', ' — ', '\t', ' | ', '  ']

        for line_block in lines:
            text = line_block.get('Text', '').strip()
            if not text:
                continue

            for sep in separators:
                if sep in text:
                    parts = text.split(sep, 1)
                    if len(parts) == 2:
                        left = parts[0].strip()
                        right = parts[1].strip()

                        # Skip if either side is too long or empty
                        if not left or not right:
                            continue
                        if len(left) > 100 or len(right) > 100:
                            continue

                        confidence = line_block.get('Confidence', 0) / 100.0

                        pairs.append({
                            'source': left,
                            'target': right,
                            'confidence': round(confidence, 2),
                            'notes': '',
                        })
                        break

        return pairs
