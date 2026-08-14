# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations
import os,tempfile,unittest
from pathlib import Path
from iot_ai.util import PathSecurityError,open_secure,resolve_within_allowed_roots,sha256_file
class SecureFileHashTests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'ok.txt').write_text('ok')
 def tearDown(self): self.tmp.cleanup()
 def test_regular_file(self): self.assertEqual(len(sha256_file(self.root/'ok.txt',allowed_roots=[self.root])),64)
 def test_outside_root(self):
  other=Path(tempfile.mkdtemp())/'x';other.write_text('x')
  try:
   with self.assertRaises(PathSecurityError): sha256_file(other,allowed_roots=[self.root])
  finally: other.unlink();other.parent.rmdir()
 def test_final_symlink(self):
  link=self.root/'link'
  try: link.symlink_to(self.root/'ok.txt')
  except (OSError,NotImplementedError): self.skipTest('symlink unavailable')
  with self.assertRaises(PathSecurityError): sha256_file(link,allowed_roots=[self.root])
 def test_directory(self):
  with self.assertRaises(PathSecurityError): sha256_file(self.root,allowed_roots=[self.root])
 def test_max_bytes(self):
  with self.assertRaises(PathSecurityError): sha256_file(self.root/'ok.txt',allowed_roots=[self.root],max_bytes=1)
 def test_root_not_trusted(self):
  with self.assertRaises(PathSecurityError): sha256_file(self.root/'ok.txt',allowed_roots=[Path(self.root.anchor)])
 def test_resolve_rejects_parent_escape(self):
  escaped=self.root/'..'/'escape.txt'
  with self.assertRaises(PathSecurityError):
   resolve_within_allowed_roots(escaped,self.root,must_exist=False)
 def test_resolve_accepts_confined_new_file(self):
  target=self.root/'report.json'
  resolved=resolve_within_allowed_roots(target,self.root,must_exist=False)
  self.assertEqual(resolved,self.root/'report.json')
if __name__=='__main__': unittest.main()
