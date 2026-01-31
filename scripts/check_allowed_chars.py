#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import re
from pathlib import Path

# Allowed character ranges: ASCII (0-127) + common emoji ranges
# Several of the most commonly used emoji blocks are listed here, which are basically sufficient
EMOJI_RANGES = [
    (0x1F300, 0x1F5FF),   # Symbols and Pictographs
    (0x1F600, 0x1F64F),   # Emoticons (Emoji)
    (0x1F680, 0x1F6FF),   # Transport and Map Symbols
    (0x1F900, 0x1F9FF),   # Supplemental Symbols and Pictographs
    (0x2600,  0x26FF),    # Miscellaneous Symbols (part of common emojis)
    (0x2700,  0x27BF),    # Dingbats (Decorative Symbols)
]

# Extra allowed non-ASCII ranges for documentation and code:
# - Latin-1 Supplement: U+0080–U+00FF (includes ×, ², etc.)
# - General Punctuation: U+2000–U+206F (includes —, –, etc.)
# - Letterlike Symbols: U+2100–U+214F (includes ℹ, etc.)
# - Arrows: U+2190–U+21FF (includes →, ←, ↑, ↓)
# - Mathematical Operators: U+2200–U+22FF (includes ≤, ≥, etc.)
# - Miscellaneous Technical: U+2300–U+23FF (includes ⏱, ⏳, etc.)
# - Box Drawing: U+2500–U+257F (includes ├, ─, │, └, ┌, ┐)
# - Geometric Shapes: U+25A0–U+25FF (includes □, etc.)
# - Miscellaneous Symbols and Arrows: U+2B00–U+2BFF (includes ⭐, etc.)
# - Variation Selectors: U+FE00–U+FE0F (emoji variation selectors)
EXTRA_ALLOWED_RANGES = [
    (0x0080, 0x00FF),     # Latin-1 Supplement
    (0x2000, 0x206F),     # General Punctuation
    (0x2100, 0x214F),     # Letterlike Symbols
    (0x2190, 0x21FF),     # Arrows
    (0x2200, 0x22FF),     # Mathematical Operators
    (0x2300, 0x23FF),     # Miscellaneous Technical
    (0x2500, 0x257F),     # Box Drawing
    (0x25A0, 0x25FF),     # Geometric Shapes
    (0x2B00, 0x2BFF),     # Miscellaneous Symbols and Arrows
    (0xFE00, 0xFE0F),     # Variation Selectors
]

def is_allowed_char(c: str) -> bool:
    code = ord(c)
    if code <= 127:  # ASCII characters are allowed
        return True
    
    # Allow extra non-ASCII blocks
    for start, end in EXTRA_ALLOWED_RANGES:
        if start <= code <= end:
            return True
    
    # Allow common emoji ranges
    for start, end in EMOJI_RANGES:
        if start <= code <= end:
            return True
    
    return False

def check_file(path: str) -> list[str]:
    problems = []
    try:
        content = Path(path).read_text(encoding="utf-8")
        for i, char in enumerate(content, 1):
            if not is_allowed_char(char):
                problems.append(f"Illegal character at position {i}: {char!r} (U+{ord(char):04X})")
                if len(problems) >= 5:  # Do not output too many results
                    break
    except Exception as e:
        problems.append(f"Failed to read file: {e}")
    return problems

def check_files() -> int:
    files = sys.argv[1:] if len(sys.argv) > 1 else []
    has_error = False

    for fname in files:
        problems = check_file(fname)
        if problems:
            has_error = True
            print(f"\nFile {fname} contains illegal characters (non-ASCII and non-emoji):")
            for p in problems:
                print("  " + p)

    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(check_files())
