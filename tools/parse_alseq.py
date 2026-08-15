#!/usr/bin/env python3
"""Parse decompressed audio blobs for ALSeqFile-like headers and sequence offsets.

Usage:
  python3 tools/parse_alseq.py [in_dir] [out_json]

Defaults:
  in_dir: out_audio_dec
  out_json: out_audio_dec/alseq_summary.json

Heuristics:
- Reads first u32 as `seqCount` (big-endian). Tries two candidate entry sizes:
  - 4 bytes per entry (array of u32 offsets)
  - 8 bytes per entry (struct of two u32s; first treated as offset)
- Marks a file as ALSeqFile-like when a significant fraction of parsed offsets
  fall inside a plausible ROM range (0x0100000..0x02000000) or as local offsets
  inside the decompressed blob.
"""
import os
import sys
import struct
import json
from pathlib import Path


ROM_MIN = 0x0100000
ROM_MAX = 0x02000000


def read_bytes(path: Path):
    with path.open("rb") as f:
        return f.read()


def try_parse_alseq(data: bytes):
    if len(data) < 4:
        return None
    try:
        seq_count = struct.unpack_from(">I", data, 0)[0]
    except struct.error:
        return None

    # sanity
    if seq_count == 0 or seq_count > 10000:
        return None

    results = []

    # Try 4-byte entries (simple offsets array)
    if len(data) >= 4 + 4 * seq_count:
        offsets4 = []
        for i in range(seq_count):
            off = struct.unpack_from(">I", data, 4 + i * 4)[0]
            offsets4.append(off)
        rom_hits = sum(1 for o in offsets4 if ROM_MIN <= o < ROM_MAX)
        local_hits = sum(1 for o in offsets4 if 0 <= o < len(data))
        results.append({
            "entry_size": 4,
            "seq_count": seq_count,
            "rom_hits": rom_hits,
            "local_hits": local_hits,
            "offsets": offsets4[:min(20, len(offsets4))],
        })

    # Try 8-byte entries (pairs) where first dword is offset
    if len(data) >= 4 + 8 * seq_count:
        offsets8 = []
        for i in range(seq_count):
            off = struct.unpack_from(">I", data, 4 + i * 8)[0]
            offsets8.append(off)
        rom_hits = sum(1 for o in offsets8 if ROM_MIN <= o < ROM_MAX)
        local_hits = sum(1 for o in offsets8 if 0 <= o < len(data))
        results.append({
            "entry_size": 8,
            "seq_count": seq_count,
            "rom_hits": rom_hits,
            "local_hits": local_hits,
            "offsets": offsets8[:min(20, len(offsets8))],
        })

    if not results:
        return None

    # Pick best candidate: prefer one with more ROM hits or local hits
    best = max(results, key=lambda r: (r["rom_hits"], r["local_hits"]))

    # Heuristic threshold: at least 20% hits or >=3 hits
    threshold = max(3, int(0.2 * best["seq_count"]))
    if best["rom_hits"] >= threshold or best["local_hits"] >= threshold:
        return best

    return None


def scan_directory(in_dir: Path):
    out = []
    for p in sorted(in_dir.rglob("*")):
        if p.is_dir():
            continue
        data = read_bytes(p)
        candidate = try_parse_alseq(data)
        if candidate:
            # Convert offsets to hex strings for compactness
            offs_hex = [f"0x{o:08X}" for o in candidate["offsets"]]
            out.append({
                "file": str(p),
                "seq_count": candidate["seq_count"],
                "entry_size": candidate["entry_size"],
                "rom_hits": candidate["rom_hits"],
                "local_hits": candidate["local_hits"],
                "sample_offsets": offs_hex,
            })
    return out


def main(argv):
    in_dir = Path(argv[1]) if len(argv) > 1 else Path("out_audio_dec")
    out_json = Path(argv[2]) if len(argv) > 2 else Path("out_audio_dec/alseq_summary.json")

    if not in_dir.exists():
        print(f"Input directory not found: {in_dir}")
        return 2

    summary = scan_directory(in_dir)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2))
    print(f"Found {len(summary)} ALSeq-like files. Wrote {out_json}")
    for item in summary:
        print(f"{item['file']}: seq_count={item['seq_count']} entry_size={item['entry_size']} rom_hits={item['rom_hits']} local_hits={item['local_hits']}")

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
