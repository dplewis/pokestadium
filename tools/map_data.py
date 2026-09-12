#!/usr/bin/env python3
"""Map a segment's .data/.bss symbols against their C declarations.

Prints, per symbol: address, actual extent, the `extern` declaration found in
the segment's C sources, and which functions reference it. Flags declarations
whose size disagrees with the symbol's real extent -- the usual cause of a
wrong-width load (`lh` where the target has `lhu`) during matching.

Usage:
    ./tools/map_data.py 1                 # fragment 1
    ./tools/map_data.py 1 --markdown      # emit a document
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMENT = re.compile(r"/\*(.*?)\*/")
HEX = re.compile(r"\b([0-9A-Fa-f]{8})\b")
DLABEL = re.compile(r"^dlabel\s+(\S+)")
SPACE = re.compile(r"\.space\s+(0x[0-9A-Fa-f]+|\d+)")
EXTERN = re.compile(r"\s*extern\s+(.+?)\s+(D_[0-9A-F]{8})\s*(\[[^\]]*\])?\s*;")

SCALAR = {"u8": 1, "s8": 1, "char": 1, "u16": 2, "s16": 2,
          "u32": 4, "s32": 4, "f32": 4, "void*": 4, "OSMesg": 4}


def vram_of(line):
    """Pick the vram out of a spimdisasm comment.

    The comment is `/* ROM VRAM */` or `/* ROM VRAM VALUE */`, so match on the
    0x8... range rather than field position -- the value column will otherwise
    silently drop every symbol whose first entry is a .word.
    """
    c = COMMENT.search(line)
    if not c:
        return None
    for tok in HEX.findall(c.group(1)):
        if tok[0] == "8":
            return int(tok, 16)
    return None


def parse(path, is_bss):
    syms, cur = [], None
    for line in path.read_text().splitlines():
        m = DLABEL.match(line)
        if m:
            cur = {"name": m.group(1), "vram": None, "space": 0, "kinds": set()}
            syms.append(cur)
            continue
        if cur is None:
            continue
        v = vram_of(line)
        if v is not None and cur["vram"] is None:
            cur["vram"] = v
        sp = SPACE.search(line)
        if sp:
            g = sp.group(1)
            cur["space"] += int(g, 16 if g.startswith("0x") else 10)
        for k in (".float", ".word", ".short", ".byte", ".double", ".asciz"):
            if k in line:
                cur["kinds"].add(k.lstrip("."))
    out = []
    for j, s in enumerate(syms):
        if s["vram"] is None and not is_bss:
            continue
        if is_bss:
            size = s["space"]
        else:
            nxt = next((t["vram"] for t in syms[j + 1:] if t["vram"] is not None), None)
            size = (nxt - s["vram"]) if nxt else 0
        out.append((s["name"], s["vram"], size, sorted(s["kinds"])))
    return out


def declared_size(decl):
    """Bytes a declaration implies, or None when it cannot be determined."""
    m = re.match(r"(\w+\*?)\s*\[(0x[0-9A-Fa-f]+|\d+)\]$", decl)
    if m and m.group(1) in SCALAR:
        n = m.group(2)
        return SCALAR[m.group(1)] * int(n, 16 if n.startswith("0x") else 10)
    if decl in SCALAR:
        return SCALAR[decl]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fragment")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()

    data = ROOT / f"asm/us/data/fragments/{args.fragment}"
    src = ROOT / f"src/fragments/{args.fragment}"
    nm = ROOT / f"asm/us/nonmatchings/fragments/{args.fragment}"
    if not data.is_dir():
        sys.exit(f"error: {data} not found")

    decls = {}
    for f in sorted(src.glob("*.c")):
        for line in f.read_text().splitlines():
            m = EXTERN.match(line)
            if m:
                decls.setdefault(m.group(2), (m.group(1) + (m.group(3) or ""), f.name))

    def users(name):
        hits = []
        for root, pat in ((src, "*.c"), (nm, "*.s")):
            r = subprocess.run(["grep", "-rl", "--include=" + pat, r"\b" + name + r"\b", str(root)],
                               capture_output=True, text=True)
            hits += [Path(p).stem.replace(f"fragment{args.fragment}_", "") for p in r.stdout.split()]
        return sorted(set(hits))

    files = sorted(data.glob("*.data.s")) + sorted(data.glob("*.bss.s"))
    mism, undecl, total = [], [], 0

    for p in files:
        is_bss = p.name.endswith(".bss.s")
        syms = parse(p, is_bss)
        total += len(syms)
        if args.markdown:
            print(f"\n### `{p.name}` — {len(syms)} symbols\n")
            print("| symbol | vram | size | declared | contents | referenced by |")
            print("|---|---|---|---|---|---|")
        else:
            print(f"\n## {p.name}  ({len(syms)} symbols)")
        for name, vram, size, kinds in syms:
            decl = decls.get(name, ("", ""))[0]
            if not decl:
                undecl.append(name)
            ds = declared_size(decl) if decl else None
            if ds is not None and size and ds != size:
                mism.append((name, decl, ds, size))
            u = ", ".join(users(name)[:4])
            if args.markdown:
                flag = " ⚠" if (ds is not None and size and ds != size) else ""
                print(f"| `{name}` | `0x{vram:08X}` | `0x{size:X}` | `{decl or '—'}`{flag} "
                      f"| {', '.join(kinds) or '—'} | {u or '—'} |")
            else:
                print(f"{name:<16} 0x{vram:08X} {'0x%X'%size:>8}  {decl:<26} {u}")

    hdr = "\n## Size disagreements\n" if args.markdown else "\n=== size disagreements ==="
    print(hdr)
    if args.markdown:
        print("| symbol | declared | implies | actual |")
        print("|---|---|---|---|")
        for n, d, ds, sz in mism:
            print(f"| `{n}` | `{d}` | `0x{ds:X}` | `0x{sz:X}` |")
    else:
        for n, d, ds, sz in mism:
            print(f"  {n}  {d:<24} implies 0x{ds:X}, actual 0x{sz:X}")
    print(f"\n{total} symbols, {len(mism)} size disagreements, {len(undecl)} undeclared.")


if __name__ == "__main__":
    sys.exit(main())
