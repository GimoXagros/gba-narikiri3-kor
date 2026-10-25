"""Reject unsafe line-layout profiles before any ROM file is written."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from v13a_reflow import apply_reflow


class ReflowGuards(unittest.TestCase):
    def run_profile(self,base,writes,count=None):
        profile={'writes':writes,'adopted_unique_lf':len(writes) if count is None else count,
                 'joined_space_offsets':[r['offset']-2 for r in writes if r['payload_hex']=='18']}
        with patch('v13a_reflow.read',side_effect=lambda name: [] if name=='linebreaks.json' else profile):
            return apply_reflow(base)[0]

    def test_existing_separator_is_not_duplicated(self):
        base=b'A\x81\x40\nB\nC\x00'
        result=self.run_profile(base,[{'offset':3,'payload_hex':'18'},{'offset':5,'payload_hex':'17'}])
        self.assertEqual(result,b'A\x16\x01\x18B\x17C\x00')
        self.assertEqual(len(result),len(base))

    def test_rejects_overlap_wrong_source_and_unapproved_controls(self):
        row={'offset':1,'payload_hex':'17'}
        for base,rows,count in [(b'A\nB',[row,row],2),(b'AXB',[row],1),
                                (b'A\nB',[row],2),(b'A\nB',[row|{'payload_hex':'00'}],1),
                                (b'A\nB',[row|{'payload_hex':'18'}],1)]:
            with self.subTest(base=base,rows=rows,count=count),self.assertRaises(ValueError):
                self.run_profile(base,rows,count)


if __name__=='__main__':unittest.main()
