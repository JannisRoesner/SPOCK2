"""Tests für eingebettete Identity-H-Schriften (CID = Glyph-ID)."""

from __future__ import annotations

from spock2.printing.receipt_fonts import build_receipt_fonts, clear_font_cache


def test_identity_h_encodes_glyph_ids_not_unicode() -> None:
    clear_font_cache()
    fonts = build_receipt_fonts("ABCä")
    regular = fonts.regular
    assert regular.unicode_to_gid[ord("A")] != ord("A")
    assert regular.unicode_to_gid[ord("ä")] != ord("ä")
    assert regular.pdf_hex_text("A") != b"<0041>"
    assert regular.pdf_hex_text("A") != regular.pdf_hex_text("B")
    gid_a = regular.unicode_to_gid[ord("A")]
    gid_space = regular.unicode_to_gid[ord(" ")]
    assert gid_a > 0
    assert gid_space > 0
    assert regular.pdf_hex_text("A ") == f"<{gid_a:04X}{gid_space:04X}>".encode("ascii")
