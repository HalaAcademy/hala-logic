"""Profile tài liệu phải phủ đúng danh mục build, không có tên ELF/test giả."""
from pathlib import Path
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'host'))
from config import catalog


class WaveformProfiles(unittest.TestCase):
    def test_every_example_has_correct_elf_and_existing_test(self):
        entries=catalog()
        files=list((ROOT/'configs/waveforms').glob('*.json'))
        self.assertEqual({p.stem for p in files},{e['key'] for e in entries})
        for entry in entries:
            with self.subTest(example=entry['key']):
                profile=json.loads((ROOT/'configs/waveforms'/f"{entry['key']}.json").read_text())
                self.assertEqual(profile['example'],entry['key'])
                self.assertEqual(profile['elf'],f"build/{entry['image']}.elf")
                self.assertEqual(profile['protocol'],entry['protocol'])
                self.assertTrue((ROOT/profile['test_module']).is_file())
                if entry['direction']!='fault':
                    self.assertIn(profile['decode_bit'],(0,8))
                    self.assertEqual(profile['baud'],entry['baud'])
                    self.assertTrue(profile['capture_stem'])
