#!/usr/bin/env python3
"""Install the official Node 22 x86_64 build into the project, without root."""

import hashlib
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = "https://nodejs.org/dist/latest-v22.x/"
checksums = urllib.request.urlopen(base + "SHASUMS256.txt", timeout=60).read().decode()
digest, filename = next(
    line.split()
    for line in checksums.splitlines()
    if line.endswith("-linux-x64.tar.xz")
)
with tempfile.TemporaryDirectory() as tmp:
    archive = Path(tmp) / filename
    urllib.request.urlretrieve(base + filename, archive)
    with archive.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != digest:
            raise RuntimeError("Node download checksum mismatch")
    with tarfile.open(archive) as source:
        source.extractall(tmp, filter="data")
    target = root / ".tools/node"
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(Path(tmp) / filename.removesuffix(".tar.xz")), target)
print("Installed official Node 22 into .tools/node")
