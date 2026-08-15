# func_800373D8 — Audio initialization: data map and archive descriptions

This document maps the important data structures, global variables, heap allocations, and absolute ROM offsets used by `func_800373D8` in `src/373A0.c`. It also gives a concise description for each archive read by the function.

## Overview
- Purpose: initialize audio heap and load multiple audio/sequence archives from ROM into heap memory, decompress Yay0-compressed blocks, and build `ALSeqFile` tables used by the audio subsystem.
- Return: heap usage in bytes: `D_800FC810->cur - D_800FC810->base`.

## Key globals allocated/used in the function
- `D_800B32A0` — statically-sized buffer (0x493E0) used as audio heap backing during init (passed to audio init struct).
- `D_800FC6DC` — temporary buffer allocated via `alHeapAlloc(..., 1, 0x61A8)` and used to copy ROM file bytes before decompression.
- `D_800FC798` — pointer table allocated `alHeapAlloc(..., 8, 4)` used as a small header/TOC workspace.
- `D_800FC6E0` — array allocated `alHeapAlloc(..., 7, 4)` that stores 7 ROM offsets read from ROM base table at `0x15C0000` (see ROM table below).
- `D_800FC6E4` — File1Header-like structure (allocated sized: header words + num_files) holding first archive's header and file offsets.
- `D_800FC6DC` — reused as buffer pointer for reading files (see above).
- `D_800FC684` — allocated `0x4120` — target buffer for decompressed first file (wave table memory).
- `D_800FC680` — allocated `0x98D8` — reserved workspace for sequencer or audio tables.
- `D_800FC6E8` — `ALSeqFile*` area holding sequence table for the second archive.
- `D_800FC6EC` — `File2SubHeader1*` used to hold sub-header for archive->seqArray[0].
- `D_800FC688`, `D_800FC68C`, `D_800FC690`, `D_800FC6AC` — per-archive decompressed buffers (sizes: 0xBB8, 0x157C, 0x2EE0, 0x9C4 respectively).
- `D_800FC6F0`, `D_800FC6FC` — `File2SubHeader2*` style arrays for other sub-archives; both have their offsets adjusted to absolute addresses.
- `D_800FC6F4`, `D_800FC6F8`, `D_800FC700`, `D_800FC704`, `D_800FC708`, `D_800FC714` — `ALSeqFile*` tables created with `alSeqFileNew()` for several sequence archives.
- `D_800FC6D8` — allocated `0xB80` words for a temporary audio table (s16* typed globally).
- `D_800FC6D4` — allocated `0x1388`, loaded from main list (archive 5 area).
- `D_800FC6CC` — allocated `0x100`, loaded from main list (archive 6 area); then each entry's `unk_00` had `D_800FC6E0[6]` added (fixing pointers to absolute ROM addresses).
- `D_800FC6D0` — allocated `0x2328`.

## Helper/utility calls and their roles
- `func_80038B68(&sp38)` — initializes audio subsystem using fields in `sp38` (heap pointer, sizes, buffers).
- `func_8004AD40(2)` — likely sets some audio mode/state.
- `alHeapAlloc(heap, n, size)` — audio heap allocator used repeatedly.
- `func_8004ADB0(rom_addr, dst, size)` — copies `size` bytes from ROM address `rom_addr` into `dst` (host memory / heap).
- `func_80037360(dst_u32ptr, base, count)` — adds `base` to `count` consecutive u32 entries starting at `dst_u32ptr`; used to convert ROM-relative offsets into absolute ROM addresses.
- `func_80050B40(src, dst, decompressed_size)` — Yay0 decompression helper (decompresses from `src` into `dst`, expecting `decompressed_size`).
- `func_8003979C`, `func_800397BC` — post-process loaders for decompressed wave tables / audio data.
- `alSeqFileNew(ALSeqFile*, rom_offset)` — initialize an `ALSeqFile` structure in heap using ROM pointer (it expects seq entries after the provided pointer).
- `func_8004AE90(channel, param)` — configures audio mixer/voice routing.

## ROM table and absolute offsets referenced
The code first reads a small ROM table at absolute address `0x015C0000` into `D_800FC6E0` (7 entries). The entries are then adjusted to absolute ROM addresses with `func_80037360`.

The following *absolute ROM offsets* are read or referenced (appearing literally in `func_800373D8`):

- 0x015C0000 — main audio archive pointer table (7 u32 pointers). The function reads 7 pointers from here into `D_800FC6E0`.
- 0x15C0160 — Yay0-compressed first file in the main archive (copied into `D_800FC6DC`, decompressed into `D_800FC684` of size 0x4120). This first decompressed file appears to hold N64 wave tables (used by sequencer).
- 0x16F27E0 — second archive header (loaded into `D_800FC6E8`, an `ALSeqFile` table).
- 0x16F2804 — first sub-header for the second archive (read into `D_800FC6EC`, a `File2SubHeader1`), used to locate two files at offsets `offset1` and `offset2`.
- 0x16F2814 — the first sub-file (copied to `D_800FC6DC`, decompressed into `D_800FC688` size 0xBB8).
- 0x16F2BD0 — the second sub-file from that sub-header (copied to `D_800FC6DC`, decompressed into `D_800FC68C` size 0x157C).
- 0x1722F74 — archive 2 sub file 2 area used to compute `D_800FC6F0` and then decompress into `D_800FC690` (0x2EE0 dest).
- 0x17C9C24 — second seq array; loaded into `D_800FC6FC` (File2SubHeader2-style) and decompressed into `D_800FC6AC` (size 0x9C4).
- 0x17DC304 — seq header (seqArray[3]) — loaded into `D_800FC6F4` and `alSeqFileNew` called.
- 0x1850C20 — nested seq header (from `D_800FC6F4->seqArray[1]`) — loaded into `D_800FC6F8` and `alSeqFileNew` called.
- 0x1978820 — archive loaded into `D_800FC700` and `alSeqFileNew` called.
- 0x197C1E0 — archive loaded into `D_800FC704` and `alSeqFileNew` called.
- 0x197C1FC — fourth archive's first seq (loaded into `D_800FC708`)
- 0x1A2AD20 — fourth archive's third seq (loaded into `D_800FC714`)
- 0x1FBA260 — main archive 5 (copied into `D_800FC6D4`, size = `D_800FC6E0[6] - D_800FC6E0[5]`)
- 0x1FBB220 — main archive 6 (copied into `D_800FC6CC`, size 0x100), then `D_800FC6CC[i].unk_00` is adjusted by adding `D_800FC6E0[6]` for 32 entries.

> Note: Many addresses are discovered in `src/373A0.c` (see function) and were added to `yamls/us/rom.yaml` as `audio_archives` entries so the extractor can pull the same regions from the ROM.

## Per-archive descriptions (what the code uses each archive for)

- `audio_main_archive` (ROM 0x015C0000 -> entries):
  - Role: master archive list for early audio resources.
  - Contents: header/TOC pointing to a first file (Yay0 compressed) that contains wave tables and other small audio data; several other files used early by the audio init.
  - Heap targets: `D_800FC6E4` (header + file pointer list), `D_800FC6DC` (tmp copy), `D_800FC684` (decompressed wave tables).

- `audio_archive_1` (ROM 0x16F27E0 and subfiles at 0x16F2804/0x16F2814/0x16F2BD0):
  - Role: sequence/AL sequence table and two Yay0-compressed data files.
  - Contents: `ALSeqFile` table (`D_800FC6E8`), a subheader (File2SubHeader1) listing at least two files: the first (probably small instrument/wavetable or driver config) and second (wave tables or supplementary audio data).
  - Heap targets: `D_800FC6EC`, `D_800FC688`, `D_800FC68C`.

- `audio_archive_2` (ROM 0x1722F74):
  - Role: another sub-archive referenced from `audio_archive_1` seq entries; used to load a larger chunk (decompressed into `D_800FC690`).
  - Heap target: `D_800FC690` (size 0x2EE0).

- `audio_archive_3` (ROM 0x17C9C24):
  - Role: sequence array for additional sequences; treated like File2SubHeader2 (num_files -> list of file offsets).
  - Heap target: `D_800FC6FC` and decompressed `D_800FC6AC`.

- `audio_archive_4` (ROM 0x17DC304 and nested at 0x1850C20):
  - Role: sequence file(s) — `D_800FC6F4` and `D_800FC6F8` become `ALSeqFile` instances.
  - Heap targets: `D_800FC6F4`, `D_800FC6F8`.

- `audio_archive_5` (ROM 0x1978820):
  - Role: third archive that provides more `ALSeqData` entries — loaded into `D_800FC700` and used by `alSeqFileNew`.

- `audio_archive_6` (ROM 0x197C1E0 / 0x197C1FC / 0x1A2AD20):
  - Role: fourth archive with several seq arrays — `D_800FC704`, `D_800FC708`, `D_800FC714`.
  - Heap targets: `D_800FC704`, `D_800FC708`, `D_800FC714`.

- `audio_archive_7` (ROM 0x1FBA260):
  - Role: a larger archive loaded into `D_800FC6D4` (size computed from pointer table). Likely contains more instrument/wave data.

- `audio_archive_8` (ROM 0x1FBB220):
  - Role: a small archive loaded into `D_800FC6CC` (0x100) containing 32 entries; the code adds `D_800FC6E0[6]` to each entry's `unk_00` field to make them absolute pointers (so this area probably stores per-file offsets relative to a base).

## Notes and hints for further reverse engineering
- The function uses several helper structs not defined in this file: `FileHeaders`, `File1Header`, `File2SubHeader1`, `File2SubHeader2`, `ALSeqFile`, `ALSeqData`. Inspect their definitions (e.g., `src/3FB0.h` and other headers) to map exact fields and sizes.
- The decompressed buffers sizes (0x4120, 0xBB8, 0x157C, 0x2EE0, 0x9C4, etc.) match the `func_80050B40(..., decompressed_size)` calls — use these sizes to validate decompression outputs.
- Many entries are processed with `func_80037360` (adds base offset) — this consistently converts stored relative offsets to absolute ROM addresses. When matching entries in the extracted bins, apply that same logic.
- `alSeqFileNew()` expects an in-memory `ALSeqFile` structure laid out as in the N64 `libaudio` format. Decompressed binary blobs that feed `alSeqFileNew` are likely standard `ALSeqFile` tables (sequence offsets + seq data). Tools that parse libaudio's seq/wave formats will be useful.

## Quick mapping table (compact)

| ROM offset | Symbol / Name | Role | Heap target |
|---:|---|---|---|
| 0x015C0000 | master pointer table | list of 7 archive offsets -> `D_800FC6E0` | `D_800FC6E0` |
| 0x15C0160 | main-archive file 1 (Yay0) | decompressed wave tables | `D_800FC6DC` -> `D_800FC684` (0x4120)
| 0x16F27E0 | seq archive header | `ALSeqFile` table | `D_800FC6E8`
| 0x16F2804 | sub-header (File2SubHeader1) | points to two files | `D_800FC6EC`
| 0x16F2814 | sub-file 1 | Yay0 -> `D_800FC688` (0xBB8) | `D_800FC688`
| 0x16F2BD0 | sub-file 2 | Yay0 -> `D_800FC68C` (0x157C) | `D_800FC68C`
| 0x1722F74 | archive sub file 2 area | contains files -> `D_800FC6F0` | `D_800FC690` (0x2EE0)
| 0x17C9C24 | second seq array | File2SubHeader2 -> `D_800FC6FC` | `D_800FC6AC` (0x9C4)
| 0x17DC304 | seq header (seqArray[3]) | `ALSeqFile` -> `D_800FC6F4` | `D_800FC6F4`
| 0x1850C20 | nested seq header | `ALSeqFile` -> `D_800FC6F8` | `D_800FC6F8`
| 0x1978820 | third archive | seq / data -> `D_800FC700` | `D_800FC700`
| 0x197C1E0 | fourth archive | seq / data -> `D_800FC704` | `D_800FC704`
| 0x197C1FC | 4th archive seq0 | `ALSeqFile` -> `D_800FC708` | `D_800FC708`
| 0x1A2AD20 | 4th archive seq2 | `ALSeqFile` -> `D_800FC714` | `D_800FC714`
| 0x1FBA260 | main archive 5 | copied to `D_800FC6D4` | `D_800FC6D4` (0x1388)
| 0x1FBB220 | main archive 6 | small table (32 entries) -> `D_800FC6CC` (0x100) | `D_800FC6CC`

---
If you want, I can:
- Add hex ranges and lengths for each ROM region in `yamls/us/rom.yaml` (already partially added).
- Produce a small Python script that parses the extracted/decompressed `out_audio_dec/<name>/` files to identify `ALSeqFile` headers and list sequence offsets.
- Annotate the C source (`src/373A0.c`) with inline comments linking to this doc.

File created: `docs/func_800373D8_audio_archives.md`
