"""Hồi quy cho các lỗi tài liệu/danh mục mà lần kiểm cũ bỏ sót."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from check_repo import documentation_errors, example_errors


class RepositoryChecks(unittest.TestCase):
    def test_nested_markdown_links_checked_but_fenced_examples_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            doc = root / 'docs/technical/plan.md'
            doc.parent.mkdir(parents=True)
            doc.write_text('[trạng thái](missing.md)\n```md\n[ví dụ](not-a-link.md)\n```\n', encoding='utf-8')
            errors, count = documentation_errors(root)
            self.assertEqual(count, 1)
            self.assertEqual(errors, ['Link hỏng docs/technical/plan.md: missing.md'])

    def test_orphan_example_and_missing_instructions_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'examples/uart/receive/main.c'
            source.parent.mkdir(parents=True)
            source.touch()
            errors = example_errors(root, [])
            self.assertEqual(errors, ['Ví dụ ngoài danh mục: examples/uart/receive/main.c'])
            errors = example_errors(root, [{'source': 'examples/uart/receive/main.c'}])
            self.assertEqual(len(errors), 2)
            self.assertTrue(any('README.md' in e for e in errors))
            self.assertTrue(any('Makefile' in e for e in errors))
