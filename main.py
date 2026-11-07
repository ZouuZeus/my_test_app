"""
Made with love by HamZeus
"""

import math
import os
import struct
import sys


# ---------------------------------------------------------------------------
# IEEE 754 double-packing helper
# ---------------------------------------------------------------------------

def _make_double(lo_dword: int, hi_dword: int) -> float:
    """Pack two 32-bit little-endian dwords into an IEEE 754 double."""
    raw = struct.pack("<II", lo_dword, hi_dword)
    return struct.unpack("<d", raw)[0]


# ---------------------------------------------------------------------------
# Product-family constant tables  (from InitializeResetToolForm @ 0x4054c0)
# ---------------------------------------------------------------------------
# Each mode has:
#   usage_count_wchar  – a hard-coded 16-bit usage-count baseline
#   multiplier        – the IEEE 754 multiplication factor
#
# Layout in the binary (param_1 offsets):
#   +0x3C  wchar_t   usage_count_wchar
#   +0x40  double    multiplier
#
# Mode          wchar   multiplier (lo, hi)
# ─────────────────────────────────────────────
# First   0x0450  0x1EB851EC  0x409E4A85
# Second  0x03ED  0xD052934B  0x406839ED
# Third   0x038F  0x1EB851EC  0x40901185

FAMILY_TABLE = {
    "First": {
        "usage_count_wchar": 0x0450,          # =  1104
        "multiplier": _make_double(0x1EB851EC, 0x409E4A85),
    },
    "Second": {
        "usage_count_wchar": 0x03ED,          # =  1005
        "multiplier": _make_double(0xD052934B, 0x406839ED),
    },
    "Third": {
        "usage_count_wchar": 0x038F,          # =   911
        "multiplier": _make_double(0x1EB851EC, 0x40901185),
    },
}

CODE_PREFIX = "4343"
DEFAULT_FAMILY = "First"


def detect_family_from_device(device_number: str) -> str:
    """
    Return the family mode selected by the executable for a device number.

    Generate handler writes "First" into the Family control before running the code
    calculation. The binary contains no references that select "Second" or
    "Third" from device-number content.
    """
    if not device_number:
        raise ValueError("device number is required")
    return DEFAULT_FAMILY

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

def compute_twelve_digit_code(
    device_number: str,
    usage_count: int,
    family: str | None = None,
) -> str:
    """
    Replicates the calculation in FUN_00403bf0.

    Parameters
    ----------
    device_number : str
        The device number string entered by the user.  The binary uses the
        rightmost 6 characters and converts that suffix with __vbaR8Str.
    usage_count : int
        The usage count/Total Impressions entered by the user.  For the
        "First" family, the binary adds Int(usage_count / 100.0).
    family : str
        Optional product-family override: "First", "Second", or "Third".
        Defaults to auto-detection from the device number.

    Returns
    -------
    str
        A 12-digit code string with the binary's fixed 4343 prefix.
    """
    if family is None or family.lower() == "auto":
        family = detect_family_from_device(device_number)

    cfg = FAMILY_TABLE.get(family)
    if cfg is None:
        raise ValueError(f"Unknown family {family!r}; use First/Second/Third")

    # ── Step 1: device_last6 ──────────────────────────────────────────
    # The binary applies Right$(DeviceNumber.Text, 6), then calls __vbaR8Str
    # on that suffix.
    last6_str = device_number[-6:] if len(device_number) >= 6 else device_number
    device_last6 = float(last6_str)

    # ── Step 2: usage_divisor ──────────────────────────────────────────
    # From the disassembly at 0x00403dd0-0x00403e0d ("First" branch):
    #   FLD   [ESI+0x7C]        ; TotalImpressions as Double
    #   FDIV  [ESI+0x9C]        ; divide by 100.0
    #   CALL  __vbaFPInt        ; Int(usage_count / 100.0)
    #   FSTP  [ESI+0x84]        ; → usage_divisor
    #
    # For non-"First" families, usage_divisor = 0.0  (MOV [ESI+0x84], 0).
    if family == "First":
        usage_divisor = math.floor(float(usage_count) / 100.0)
    else:
        usage_divisor = 0

    # ── Step 3: formula ───────────────────────────────────────────────
    #   result = (usage_count_wchar + device_last6 + usage_divisor) * multiplier
    usage_count_wchar = float(cfg["usage_count_wchar"])
    multiplier = cfg["multiplier"]

    result = (usage_count_wchar + device_last6 + usage_divisor) * multiplier

    # ── Step 4: integer part → 12-digit 4343-prefixed string ─────────
    # The binary calls __vbaFPInt (VB Int/floor), then
    # overlays the fixed 4343 prefix onto the 12-digit result string.
    result_int = math.floor(result)
    result_str = str(result_int)
    numeric_code = result_str.zfill(12)[-12:]
    code = CODE_PREFIX + numeric_code[len(CODE_PREFIX):]

    # The binary then sets the result into a form control via .Text = code.
    return code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    def print_usage() -> None:
        program_name = os.path.basename(sys.argv[0]) or "password_reset.py"
        print(f"Usage: {program_name} <device_number> <usage_count>")
        print()
        print("  device_number   e.g. ABC123456789")
        print("  usage_count      e.g. 50000")

    if len(sys.argv) < 3:
        print_usage()
        print()
        # Demo with sample values
        print("─── Demo ───")
        code = compute_twelve_digit_code("ABC123456789", 50000)
        family = detect_family_from_device("ABC123456789")
        print(f"  device=ABC123456789  usage=50000  family={family:6s}  →  code={code}")
        sys.exit(0)

    if len(sys.argv) > 3:
        print("Family is detected from the device number; do not pass First/Second/Third.")
        print()
        print_usage()
        sys.exit(2)

    device = sys.argv[1]
    usage = int(sys.argv[2])

    family = detect_family_from_device(device)
    code = compute_twelve_digit_code(device, usage, family)

    print(f"device number : {device}")
    print(f"usage Count    : {usage}")
    print(f"12-Digit Code : {code}")
