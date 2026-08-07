from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export-root", type=Path, required=True)
    args = ap.parse_args()
    root = args.export_root.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    failures = []
    checked = 0
    for rec in manifest.get("files", []):
        p = root / rec["relative_path"]
        checked += 1
        if not p.exists():
            failures.append({"file": rec["relative_path"], "error": "missing"})
            continue
        if int(rec.get("bytes", -1)) != p.stat().st_size:
            failures.append({"file": rec["relative_path"], "error": "size_mismatch"})
            continue
        actual = sha256_file(p)
        if actual != rec.get("sha256"):
            failures.append({"file": rec["relative_path"], "error": "sha256_mismatch", "actual": actual})
    result = {"checked_files": checked, "failures": failures, "pass": not failures}
    print(json.dumps(result, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
