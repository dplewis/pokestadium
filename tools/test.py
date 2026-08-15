#!/usr/bin/env python3

import struct
import wave
import numpy as np

# ------------------------------
# Helpers for BE reads
# ------------------------------

def read_u8(data, o):
    return data[o]

def read_s16(data, o):
    return struct.unpack(">h", data[o:o+2])[0]

def read_u16(data, o):
    return struct.unpack(">H", data[o:o+2])[0]

def read_u32(data, o):
    return struct.unpack(">I", data[o:o+4])[0]

def write_u32(data, o, v):
    data[o:o+4] = struct.pack(">I", v)

# ------------------------------
# N64 ADPCM decode
# ------------------------------
#  - frames of 9 bytes produce 16 samples
#  - predictor book provides scale coefficients
# ------------------------------

def decode_n64_adpcm(data, book, order, npredictors):
    pcm = []
    hist1 = 0
    hist2 = 0
    pos = 0

    while pos < len(data):
        header = data[pos]
        pos += 1

        predict_index = header >> 4
        scale = header & 0x0F

        signed_nibbles = []

        for _ in range(8):
            byte = data[pos]
            pos += 1
            signed_nibbles.append((byte >> 4))
            signed_nibbles.append(byte & 0x0F)

        for n in signed_nibbles:
            if n >= 8:
                n -= 16

            coeff1 = book[predict_index][0]
            coeff2 = book[predict_index][1]

            sample = ((n << scale) << 11)
            sample += hist1 * coeff1 + hist2 * coeff2
            sample >>= 11

            hist2 = hist1
            hist1 = sample

            if sample < -32768:
                sample = -32768
            elif sample > 32767:
                sample = 32767

            pcm.append(sample)

    return np.array(pcm, dtype=np.int16)

# ------------------------------
# Parse ADPCM Book (Nintendo style)
# ------------------------------

def extract_book(data, ptr):
    order = read_s16(data, ptr + 0)
    npredictors = read_s16(data, ptr + 2)

    coeffs = []
    offset = ptr + 4
    for p in range(npredictors):
        c1 = read_s16(data, offset)
        c2 = read_s16(data, offset + 2)
        coeffs.append((c1, c2))
        offset += 8

    return coeffs, order, npredictors

# ------------------------------
# Relocation logic matches func_8003BD2C
# ------------------------------

def relocate_soundbank(data, base):
    count = read_u32(data, base + 0x20)

    wave_list_ptr = read_u32(data, base + 0x2C)
    wave_list_ptr += base

    wave_table_ptrs = []

    for i in range(count):
        tbl_ptr = read_u32(data, wave_list_ptr + i*4)
        tbl_ptr += base
        wave_table_ptrs.append(tbl_ptr)

        baseaddr = read_u32(data, tbl_ptr + 0)
        flags = read_u8(data, tbl_ptr + 9)

        if flags == 0 and (baseaddr & 0xFF000000) != 0xFF000000:
            write_u32(data, tbl_ptr + 0, baseaddr + base)
            data[tbl_ptr + 9] = 1

        wave_type = read_u8(data, tbl_ptr + 8)

        if wave_type == 2:
            book_ptr = read_u32(data, tbl_ptr + 0x10)
            write_u32(data, tbl_ptr + 0x10, base + book_ptr)

        raw_loop_ptr = read_u32(data, tbl_ptr + 0x0C)
        if raw_loop_ptr != 0:
            write_u32(data, tbl_ptr + 0x0C, base + raw_loop_ptr)

    return wave_table_ptrs

# ------------------------------
# Extract and decode waves
# ------------------------------

def decode_soundbank(filename, bank_offset=0):
    with open(filename, "rb") as f:
        data = bytearray(f.read())

    wave_ptrs = relocate_soundbank(data, bank_offset)
    console.log(wave_ptrs);
    sample_rate = 32000

    for idx, tbl in enumerate(wave_ptrs):
        baseaddr = read_u32(data, tbl + 0)
        length = read_u32(data, tbl + 4)
        wave_type = read_u8(data, tbl + 8)

        if baseaddr == 0 or length == 0:
            continue

        sample_data = data[baseaddr : baseaddr + length]

        if wave_type == 2:
            book_ptr = read_u32(data, tbl + 0x10)
            book, order, predicts = extract_book(data, book_ptr)

            pcm = decode_n64_adpcm(sample_data, book, order, predicts)

        else:
            pcm = np.frombuffer(sample_data, dtype=np.int8).astype(np.int16) * 256

        outname = f"wave_{idx:03d}.wav"
        with wave.open(outname, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm.tobytes())

        print("Decoded:", outname)

# ------------------------------
# RUN
# ------------------------------

if __name__ == "__main__":
    decode_soundbank("archive2_sound1.bin", 0)
