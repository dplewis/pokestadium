#!/usr/bin/env python3

import sys
import re
import os
from pathlib import Path
import crunch64

# Audio decompressor v0.1 (WIP)
# Usage: decompress_audio.py [path to Yay0 file]

# Read a big endian 32-bit value from a bytearray file with a given offset.
def read_32_be_value(file_arr, i):
    return (file_arr[i + 0] << 24) + (file_arr[i + 1] << 16)  \
         + (file_arr[i + 2] << 8)  + (file_arr[i + 3])

assets_path = "assets/us/"

filepath = Path(sys.argv[1])
filename = os.path.splitext(os.path.basename(filepath))[0]

file = open(filepath, 'rb')
file_header = bytearray(file.read(0x8)) # First, we need to fetch the header size. This is right after the magic part of the header.

header_size = -1
# Check for 59 61 79 30, which is "YAY0"
if file_header[0] == 0x59 and file_header[1] == 0x61 and file_header[2] == 0x79 and file_header[3] == 0x30:
    header_size = 0

# Check for 00 00 00 00 59 61 79 30
if file_header[0] == 0x00 and file_header[1] == 0x00 and file_header[2] == 0x00 and file_header[3] == 0x00 and file_header[4] == 0x59 and file_header[5] == 0x61 and file_header[6] == 0x79 and file_header[7] == 0x30:
    header_size = 4

if (header_size == -1):
    print(filepath, "File magic is NOT 'YAY0'. Please pass a valid file.")
    sys.exit(1)

file.seek(header_size, os.SEEK_SET)
yay0_file = file.read()

decompressed = crunch64.yay0.decompress(yay0_file)
file.close()
file = open(filepath, 'wb')
file.write(decompressed)
