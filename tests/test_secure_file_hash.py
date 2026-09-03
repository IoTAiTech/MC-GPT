# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations
import os,tempfile,unittest
from pathlib import Path
from iot_ai.util import PathSecurityError,_platform_root_aliases,confined_text_write,resolve_within_allowed_roots,sha256_file
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
 def test_macos_private_var_alias_is_derived_from_trusted_root(self):
  aliases=_platform_root_aliases("/private/var/folders/xx/T/tmpABC")
  self.assertIn("/var/folders/xx/T/tmpABC", aliases)
 def test_windows_drive_relative_component_is_rejected(self):
  if os.name != 'nt':
   self.skipTest('Windows drive-relative paths only')
  with self.assertRaises(PathSecurityError):
   resolve_within_allowed_roots('C:escape.txt',self.root,must_exist=False)
  with self.assertRaises(PathSecurityError):
   confined_text_write('D:out.txt','x',[self.root])
 def test_resolve_accepts_confined_new_file(self):
  target=self.root/'report.json'
  resolved=resolve_within_allowed_roots(target,self.root,must_exist=False)
  self.assertEqual(resolved.resolve(), (self.root/'report.json').resolve())
 def test_confined_write_rejects_symlink(self):
  outside=Path(tempfile.mkdtemp())/'outside.txt';outside.write_text('keep')
  link=self.root/'out.txt'
  try: link.symlink_to(outside)
  except (OSError,NotImplementedError):
   outside.unlink();outside.parent.rmdir();self.skipTest('symlink unavailable')
  try:
   with self.assertRaises(PathSecurityError): confined_text_write(link,'pwn',[self.root])
   self.assertEqual(outside.read_text(),'keep')
  finally:
   link.unlink(missing_ok=True);outside.unlink();outside.parent.rmdir()
 def test_intermediate_symlink_cannot_escape(self):
  outside=Path(tempfile.mkdtemp()); (outside/'escaped.txt').write_text('keep')
  link=self.root/'link'
  try: link.symlink_to(outside, target_is_directory=True)
  except (OSError,NotImplementedError):
   (outside/'escaped.txt').unlink(); outside.rmdir(); self.skipTest('symlink unavailable')
  try:
   with self.assertRaises(PathSecurityError):
    confined_text_write('link/escaped.txt','audit',[self.root])
   self.assertEqual((outside/'escaped.txt').read_text(),'keep')
  finally:
   link.unlink(missing_ok=True); (outside/'escaped.txt').unlink(); outside.rmdir()
 def test_presented_root_alias_is_accepted(self):
  """Caller may pass /var or 8.3 as the allowed root; I/O stays on the realpath."""
  alias_parent=Path(tempfile.mkdtemp())
  alias=alias_parent/'alias'
  try:
   alias.symlink_to(self.root, target_is_directory=True)
  except (OSError,NotImplementedError):
   alias_parent.rmdir(); self.skipTest('symlink unavailable')
  try:
   target=alias/'ok.txt'
   resolved=resolve_within_allowed_roots(target,alias,must_exist=True)
   self.assertEqual(resolved.resolve(), (self.root/'ok.txt').resolve())
   self.assertEqual(len(sha256_file(target,allowed_roots=[alias])),64)
   written=confined_text_write(alias/'alias-report.json','ok',[alias])
   self.assertEqual(written.resolve(), (self.root/'alias-report.json').resolve())
  finally:
   alias.unlink(missing_ok=True); alias_parent.rmdir()
if __name__=='__main__': unittest.main()
