#!/usr/bin/env python3
"""Record SHA-256 fingerprints of the Desk's input files in desk/.input-snapshot.json."""
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
def files():
    for pat in ["inbox/*.txt", "desk/bookings.csv", "desk/desk-rules.md", "desk/allowed-values.md",
                "desk/menu-and-dietary.md", "quote-calculator/rates.json", "reference/*"]:
        for p in sorted(root.glob(pat)):
            if p.is_file():
                yield p
snap = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files()}
(root / "desk/.input-snapshot.json").write_text(json.dumps(snap, indent=2))
print(f"Snapshot recorded for {len(snap)} files:")
for k in snap: print("  " + k)
