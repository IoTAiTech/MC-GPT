# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-09-04
"""Offline distribution contracts. These are not provider or production tests."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tomllib
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
COLLECT = runpy.run_path(str(ROOT / 'tools/package_assets.py'))['collect_public_assets']
BUILD = runpy.run_path(str(ROOT / 'tools/build_wheel.py'))['build']


def fixture_root(tmp_path):
    root = tmp_path / 'input'
    shutil.copytree(ROOT / 'skills', root / 'skills')
    (root / 'governance').mkdir()
    shutil.copy2(ROOT / 'governance/garden-skills.lock.json', root / 'governance/garden-skills.lock.json')
    shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', root / 'THIRD_PARTY_NOTICES.md')
    return root


def test_wheel_metadata_and_name_follow_project(tmp_path):
    version = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
    result = BUILD(ROOT, tmp_path)
    assert result['version'] == version
    assert f'-{version}-' in Path(result['path']).name
    with zipfile.ZipFile(result['path']) as z:
        metadata = [n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
        assert len(metadata) == 1
        assert f'\nVersion: {version}\n' in '\n'+z.read(metadata[0]).decode()


def test_wheel_members_and_records_bind_all_reviewed_assets(tmp_path):
    result = BUILD(ROOT, tmp_path)
    with zipfile.ZipFile(result['path']) as z:
        names = z.namelist()
        assert len(names) == len(set(names))
        for name, data in COLLECT(ROOT):
            assert z.read(name) == data
        record = next(n for n in names if n.endswith('.dist-info/RECORD'))
        for name, digest, size in csv.reader(io.StringIO(z.read(record).decode())):
            if name == record:
                continue
            data = z.read(name)
            assert len(data) == int(size)
            assert digest == 'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')


def test_two_clean_builds_are_identical(tmp_path):
    first=BUILD(ROOT,tmp_path/'a'); second=BUILD(ROOT,tmp_path/'b')
    assert first['sha256']==second['sha256']


def test_installed_tree_finds_skills_without_source_checkout(tmp_path):
    result=BUILD(ROOT,tmp_path/'wheel'); installed=tmp_path/'installed'; installed.mkdir()
    with zipfile.ZipFile(result['path']) as z:
        z.extractall(installed)
    # Isolated Python ignores the current repository and all user PYTHONPATH.
    code = ('import sys,json;from pathlib import Path;'
            'sys.path.insert(0,sys.argv[1]);'
            'from iot_ai.skill_registry import discover,garden_lock_path;'
            'r=discover(user_home=Path(sys.argv[2]));'
            'assert "garden-web-design" in r["skills"],r["rejected"];'
            'assert "iot-ai-web-visual-quality" in r["skills"];'
            'assert garden_lock_path().is_file();'
            'print(json.dumps({"count":r["count"],"ids":sorted(r["skills"])}))')
    p=subprocess.run([sys.executable,'-I','-c',code,str(installed),str(tmp_path/'home')],cwd=tmp_path,capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stderr
    assert json.loads(p.stdout)['count']>=10


@pytest.mark.parametrize('mutation',['tamper','missing','unlisted','script','oversized','symlink'])
def test_package_boundary_rejects_unapproved_data(tmp_path,mutation):
    r=fixture_root(tmp_path)
    skill=r/'skills/third-party/garden-web-design/SKILL.md'
    if mutation=='tamper': skill.write_text(skill.read_text()+'\nModified\n')
    elif mutation=='missing': skill.unlink()
    elif mutation=='unlisted':
        p=r/'skills/third-party/not-reviewed/SKILL.md';p.parent.mkdir();p.write_text('not reviewed')
    elif mutation=='script': (r/'skills/unreviewed.py').write_text('raise RuntimeError()')
    elif mutation=='oversized': (r/'skills/iot-ai/SKILL.md').write_text('x'*128001)
    elif mutation=='symlink':
        link=r/'skills/redirect'
        try: link.symlink_to(r/'governance',target_is_directory=True)
        except OSError: pytest.skip('platform does not permit symlink creation')
    with pytest.raises(ValueError): COLLECT(r)


def test_setuptools_source_distribution_includes_build_collector():
    manifest=(ROOT/'MANIFEST.in').read_text()
    assert 'include tools/package_assets.py' in manifest
    assert 'include setup.py' in manifest


def test_collector_never_loads_user_or_customer_skill_roots(tmp_path):
    r=fixture_root(tmp_path)
    p=r/'private/SKILL.md';p.parent.mkdir();p.write_text('not public')
    assert not any('private' in name for name,_ in COLLECT(r))
