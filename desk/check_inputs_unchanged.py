#!/usr/bin/env python3
"""Compare current input files with desk/.input-snapshot.json. Exit 1 if anything changed."""
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
sp = root / "desk/.input-snapshot.json"
if not sp.exists():
    print("No snapshot found. Run desk/snapshot_inputs.py before the run.", file=sys.stderr); sys.exit(1)
snap = json.loads(sp.read_text())
bad = []
for rel, h in snap.items():
    p = root / rel
    if not p.exists(): bad.append(f"{rel} (deleted)")
    elif hashlib.sha256(p.read_bytes()).hexdigest() != h: bad.append(f"{rel} (changed)")
if bad:
    print("INPUTS CHANGED during the run: " + ", ".join(bad) + ". Restore these files from Git and re-run.", file=sys.stderr); sys.exit(1)
print(f"Inputs unchanged ({len(snap)} files).")
