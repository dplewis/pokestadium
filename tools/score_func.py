#!/usr/bin/env python3
"""Score one function against its expected instruction stream.

Reads the expected words from a function's nonmatching .s file and the actual
words from the linked ELF, then aligns the two streams so that an inserted or
deleted instruction costs one edit instead of cascading through every following
word.

Reports the instruction count on both sides and the number of edits. A candidate
of the wrong length is called out explicitly, because matching the length is the
prerequisite for the edit count to mean anything.

Usage:
    ./tools/score_func.py func_81203C58
    ./tools/score_func.py func_81203C58 -v     # show the aligned differences
"""

import argparse
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROM = ROOT / "build" / "pokestadium-us.z64"
ASM_ROOT = ROOT / "asm" / "us" / "nonmatchings"

JR_RA = 0x03E00008
MAX_EXTRA = 256          # how far past the expected length to look for the end

# e.g.  /* 0835D8 81203C58 27BDFF98 */  addiu  $sp, $sp, -0x68
S_RE = re.compile(r"\s*/\* ([0-9A-Fa-f]{6,8}) ([0-9A-Fa-f]{8}) ([0-9A-Fa-f]{8}) \*/")


def find_asm(name):
    hits = sorted(ASM_ROOT.rglob(f"{name}.s"))
    if not hits:
        sys.exit(f"error: no .s found for {name} under {ASM_ROOT}")
    if len(hits) > 1:
        sys.exit("error: ambiguous, matches:\n  " + "\n  ".join(map(str, hits)))
    return hits[0]


def read_expected(path):
    """Return (rom_offset_of_first_instr, vaddr_of_first_instr, [words]).

    Only lines after the `glabel` count as instructions. When a segment has
    migrated rodata, the function's .s begins with a `.late_rodata` section
    holding its jump tables, and those entries look exactly like instruction
    lines -- reading them as code silently scores the wrong bytes entirely.
    """
    rows, in_text = [], False
    for line in path.read_text().splitlines():
        if line.startswith("glabel"):
            in_text = True
            continue
        if not in_text:
            continue
        m = S_RE.match(line)
        if m:
            rows.append((int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)))
    if not rows:
        sys.exit(f"error: no instruction lines parsed from {path}")
    return rows[0][0], rows[0][1], [w for _, _, w in rows]


def read_actual(rom, rom_off, expected_len):
    """Read the built function's words straight out of the ROM.

    Fragments are overlays that share vaddr space, so disassembling the ELF by
    address can land in the wrong section. The ROM offset is unambiguous. The
    function ends at `jr $ra` plus its delay slot.
    """
    words = []
    limit = expected_len + MAX_EXTRA
    for i in range(limit):
        off = rom_off + i * 4
        if off + 4 > len(rom):
            break
        w = int.from_bytes(rom[off:off + 4], "big")
        words.append(w)
        if w == JR_RA:
            off += 4
            if off + 4 <= len(rom):
                words.append(int.from_bytes(rom[off:off + 4], "big"))
            break
    return words


def check_rom_fresh(rom):
    """Refuse to score a ROM older than the sources that should have built it.

    A failed build leaves the previous ROM in place, and scoring it silently
    reports the *old* code -- which reads as a perfect match if the function was
    still behind its pragma. That has produced false "0 differences" results, so
    treat a stale ROM as a hard error rather than a warning.
    """
    rom_mtime = rom.stat().st_mtime
    newest, newest_path = 0.0, None
    for d in ("src", "include"):
        for f in (ROOT / d).rglob("*"):
            if f.suffix in (".c", ".h") and f.is_file():
                m = f.stat().st_mtime
                if m > newest:
                    newest, newest_path = m, f
    if newest > rom_mtime:
        rel = newest_path.relative_to(ROOT) if newest_path else "a source file"
        sys.exit(
            f"error: {rom.name} is older than {rel}.\n"
            "       The build failed or was not run -- scoring it would report "
            "stale code.\n"
            "       Run 'make' and check it succeeds before scoring."
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("function")
    ap.add_argument("-r", "--rom", type=Path, default=DEFAULT_ROM)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    asm = find_asm(args.function)
    rom_off, vaddr, exp_words = read_expected(asm)

    if not args.rom.exists():
        sys.exit(f"error: {args.rom} not found -- run make first")
    check_rom_fresh(args.rom)
    act_words = read_actual(args.rom.read_bytes(), rom_off, len(exp_words))

    sm = difflib.SequenceMatcher(a=exp_words, b=act_words, autojunk=False)
    edits = sum(max(i2 - i1, j2 - j1)
                for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")

    if args.verbose:
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            for k in range(max(i2 - i1, j2 - j1)):
                e = f"{exp_words[i1 + k]:08X}" if i1 + k < i2 else "--------"
                a = f"{act_words[j1 + k]:08X}" if j1 + k < j2 else "--------"
                print(f"  {vaddr + (i1 + k) * 4:08X}  expect {e}  got {a}")

    if len(act_words) != len(exp_words):
        print(f"LENGTH MISMATCH: {len(act_words)} instrs, expected {len(exp_words)} "
              f"({len(act_words) - len(exp_words):+d})")
    print(f"{edits}/{len(exp_words)} instructions differ")
    return 0 if edits == 0 and len(act_words) == len(exp_words) else 1


if __name__ == "__main__":
    sys.exit(main())
