#!/usr/bin/env python3
"""
Extractor + Yay0 decompressor for audio archives referenced in src/373A0.c.

Features:
- Cleans `out_audio/` and `out_audio_dec/` on start
- Extracts named ROM ranges to `out_audio/<name>.bin`
- Scans each extracted file for embedded `Yay0` headers and decompresses each occurrence
  into `out_audio_dec/<name>/<name>_<offset>_dec.bin`.

Usage:
  python3 tools/extract_sound_assets.py [rom_path]

Defaults:
  rom_path: build/pokestadium-us.z64

This script prefers the `crunch64` Python library for Yay0 decompression and falls back
to `tools/decompress_yay0.py` if `crunch64` is unavailable.
"""
import os
import sys
import shutil
from pathlib import Path
import subprocess


# Ordered list of (offset, name) taken from src/373A0.c and rom.yaml additions
OFFSETS = [
    (0x015C0000, "audio_main_archive"),
    (0x016F27E0, "audio_archive_1"),
    (0x016F2804, "audio_archive_1_sub"),
    (0x016F2814, "audio_archive_1_file1"),
    (0x016F2BD0, "audio_archive_1_file2"),
    (0x01722F74, "audio_archive_2"),
    (0x017C9C24, "audio_archive_3"),
    (0x017DC304, "audio_archive_4"),
    (0x01850C20, "audio_archive_4_seq2"),
    (0x01978820, "audio_archive_5"),
    (0x0197C1E0, "audio_archive_6"),
    (0x0197C1FC, "audio_archive_6_seq0"),
    (0x01A2AD20, "audio_archive_6_seq2"),
    (0x01FBA260, "audio_archive_7"),
    (0x01FBB220, "audio_archive_8"),
]

ROM_END = 0x02000000


def clean_dirs(base_out="out_audio", dec_out="out_audio_dec"):
    for p in (base_out, dec_out):
        if os.path.exists(p):
            shutil.rmtree(p)
        os.makedirs(p, exist_ok=True)


def find_yay0_offsets(data: bytes):
    magic = b"Yay0"
    offs = []
    idx = data.find(magic)
    while idx != -1:
        offs.append(idx)
        idx = data.find(magic, idx + 1)
    return offs


def try_decompress_yay0_bytes(data: bytes):
    # Try python crunch64 first
    try:
        import crunch64

        return crunch64.yay0.decompress(data)
    except Exception:
        # Fallback: write tmp input and call tools/decompress_yay0.py
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(data)
            tf.flush()
            inpath = tf.name
        outpath = inpath + ".dec"
        try:
            subprocess.check_call([sys.executable, "tools/decompress_yay0.py", inpath, outpath])
            with open(outpath, "rb") as of:
                result = of.read()
        finally:
            try:
                os.remove(inpath)
            except Exception:
                pass
            try:
                os.remove(outpath)
            except Exception:
                pass
        return result


def extract_and_decompress(rom_path: str):
    rom = Path(rom_path)
    if not rom.exists():
        print(f"ROM not found: {rom_path}")
        return 1

    clean_dirs()

    with rom.open("rb") as f:
        for i, (start, name) in enumerate(OFFSETS):
            end = OFFSETS[i + 1][0] if i + 1 < len(OFFSETS) else ROM_END
            size = end - start
            if size <= 0:
                print(f"Skipping {name} at {start:08X}: non-positive size {size}")
                continue

            f.seek(start)
            seg = f.read(size)
            out_dir = Path("out_audio")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{name}.bin"
            out_file.write_bytes(seg)
            print(f"Wrote {out_file} ({size} bytes)")

            # scan for embedded Yay0 blocks and decompress each
            yay_offs = find_yay0_offsets(seg)
            if not yay_offs:
                print(f"No Yay0 in {name}")
                continue

            dec_dir = Path("out_audio_dec") / name
            dec_dir.mkdir(parents=True, exist_ok=True)

            for off in yay_offs:
                print(f"Decompressing Yay0 at offset {off} in {name}")
                try:
                    dec = try_decompress_yay0_bytes(seg[off:])
                except Exception as e:
                    print(f"Decompression failed for {name} offset {off}: {e}")
                    continue
                out_dec = dec_dir / f"{name}_{off:08X}_dec.bin"
                out_dec.write_bytes(dec)
                print(f"Wrote {out_dec} ({len(dec)} bytes)")

    print("All done.")
    return 0


def main(argv):
    rom = argv[1] if len(argv) > 1 else "build/pokestadium-us.z64"
    return extract_and_decompress(rom)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
