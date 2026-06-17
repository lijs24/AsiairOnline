"""Unit tests for _detect_high_byte_offset byte-order detection.

The detector returns the byte offset (0=even, 1=odd) whose histogram is more
*concentrated*: in a real 16-bit astro frame the high byte sits in a narrow
range (peaked histogram) while the low byte carries the noise (flat histogram),
so the more-peaked half marks the high byte.  The synthetic frames below model
that.  No device or network is needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from asiairbridge.image_preview import _detect_high_byte_offset  # noqa: E402


def _astro_like_raw(endian: str, n: int = 4096, high: int = 0x12) -> bytes:
    """16-bit frame: near-constant high byte (concentrated histogram) + low byte
    sweeping 0..255 (flat histogram).  endian '<' puts the high byte on odd
    positions, '>' on even positions."""
    low = np.arange(n, dtype=np.uint16) % 256
    values = (np.uint16(high) << 8) | low
    return values.astype(endian + "u2").tobytes()


class TestDetectHighByteOffset:
    def test_little_endian_high_byte_at_odd_returns_1(self):
        assert _detect_high_byte_offset(_astro_like_raw("<")) == 1

    def test_big_endian_high_byte_at_even_returns_0(self):
        assert _detect_high_byte_offset(_astro_like_raw(">")) == 0

    def test_return_type_is_int(self):
        assert isinstance(_detect_high_byte_offset(_astro_like_raw("<")), int)

    def test_uniform_data_does_not_raise(self):
        # All bytes equal → both halves equally concentrated → no crash.
        assert _detect_high_byte_offset(bytes([0x80] * 8192)) in (0, 1)

    def test_concentrated_odd_byte_returns_1(self):
        # Odd byte constant (peaked), even byte sweeps (flat) → high byte is odd.
        n = 2048
        data = bytearray(n * 2)
        for i in range(n):
            data[2 * i] = i % 256
            data[2 * i + 1] = 0x12
        assert _detect_high_byte_offset(bytes(data)) == 1

    def test_concentrated_even_byte_returns_0(self):
        # Even byte constant (peaked), odd byte sweeps (flat) → high byte is even.
        n = 2048
        data = bytearray(n * 2)
        for i in range(n):
            data[2 * i] = 0x12
            data[2 * i + 1] = i % 256
        assert _detect_high_byte_offset(bytes(data)) == 0
