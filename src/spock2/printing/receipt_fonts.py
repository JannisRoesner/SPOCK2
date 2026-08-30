"""Eingebettete Monospace-Schrift für CUPS-PDF-Bons (sans-serif wie Consolas/GDI)."""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from io import BytesIO

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

# JetBrains Mono: 600/1000 em (wie Consolas/Courier in 10-pt-Layout)
_MONO_EM = 0.6
_FONT_FILES = {
    False: "JetBrainsMono-Regular.ttf",
    True: "JetBrainsMono-Bold.ttf",
}


@dataclass(frozen=True, slots=True)
class EmbeddedMonoFont:
    """Eine eingebettete Type0/CIDFontType2-Schrift für handgebaute PDFs."""

    pdf_objects: tuple[bytes, ...]
    resource_name: str  # z. B. /F1
    units_per_em: int
    glyph_width: int  # Design-Einheiten (monospace)
    unicode_to_gid: dict[int, int]

    def char_width(self, size: float) -> float:
        return size * self.glyph_width / self.units_per_em

    def text_width(self, text: str, size: float) -> float:
        return len(text) * self.char_width(size)

    def pdf_hex_text(self, text: str) -> bytes:
        """Identity-H-Hexstring: CID = Glyph-ID der Subset-TTF, nicht Unicode."""
        hexchars = "".join(f"{self.unicode_to_gid.get(ord(ch), 0):04X}" for ch in text)
        return f"<{hexchars}>".encode("ascii")


@dataclass(frozen=True, slots=True)
class ReceiptPdfFonts:
    regular: EmbeddedMonoFont
    bold: EmbeddedMonoFont

    def text_width(self, text: str, size: float) -> float:
        return self.regular.text_width(text, size)

    @property
    def mono_em(self) -> float:
        return _MONO_EM


def build_receipt_fonts(text: str) -> ReceiptPdfFonts:
    """Erzeugt Regular + Bold als eingebettete PDF-Font-Objekte."""
    chars = _unique_chars(text)
    regular = _embed_font(chars, bold=False, object_id=5, resource_name="/F1")
    bold = _embed_font(chars, bold=True, object_id=10, resource_name="/F2")
    return ReceiptPdfFonts(regular=regular, bold=bold)


def _unique_chars(text: str) -> str:
    return "".join(dict.fromkeys(ch for ch in f" {text}" if ch == " " or ch.isprintable()))


def _font_bytes(bold: bool) -> bytes:
    name = _FONT_FILES[bold]
    with resources.files("spock2.printing.fonts").joinpath(name).open("rb") as fh:
        return fh.read()


@lru_cache(maxsize=4)
def _subset_font_bytes(
    bold: bool, chars: str
) -> tuple[bytes, int, int, tuple[tuple[int, int], ...]]:
    """Subset-TTF, Metriken und Unicode→GID (nach dem kompakten Subset)."""
    raw = _font_bytes(bold)
    font = TTFont(BytesIO(raw))
    opts = Options()
    opts.drop_tables += ["GSUB", "GPOS", "fvar", "gvar", "STAT"]
    subsetter = Subsetter(opts)
    subsetter.populate(text=chars)
    subsetter.subset(font)
    out = BytesIO()
    font.save(out)
    subset_data = out.getvalue()
    units = int(font["head"].unitsPerEm)
    glyph_width = _mono_glyph_width(font)
    mapping = tuple(sorted(_cmap_to_gid(font).items()))
    return subset_data, units, glyph_width, mapping


def _cmap_to_gid(font: TTFont) -> dict[int, int]:
    cmap = font.getBestCmap() or {}
    name_to_gid = {name: gid for gid, name in enumerate(font.getGlyphOrder())}
    mapping: dict[int, int] = {}
    for code, name in cmap.items():
        gid = name_to_gid.get(name)
        if gid is not None:
            mapping[int(code)] = int(gid)
    return mapping


def _mono_glyph_width(font: TTFont) -> int:
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()
    widths = {glyph_set[cmap[code]].width for code in cmap if code in cmap}
    if not widths:
        return 600
    return int(next(iter(widths)) if len(widths) == 1 else sum(widths) / len(widths))


def _embed_font(
    chars: str,
    *,
    bold: bool,
    object_id: int,
    resource_name: str,
) -> EmbeddedMonoFont:
    ttf_data, units, glyph_width, mapping_pairs = _subset_font_bytes(bold, chars)
    unicode_to_gid = dict(mapping_pairs)
    base_name = "JBMono-Bold" if bold else "JBMono-Regular"
    font_stream = zlib.compress(ttf_data)
    descriptor_id = object_id + 2
    cid_id = object_id + 1
    stream_id = object_id + 3
    to_unicode_id = object_id + 4

    width_pt = glyph_width * 1000 // units  # skaliert für DW/W (Tausendstel em)
    w_array = _build_w_array(unicode_to_gid, width_pt)

    objects = (
        _type0_font_object(base_name=base_name, cid_id=cid_id, to_unicode_id=to_unicode_id),
        _cid_font_object(
            base_name=base_name,
            descriptor_id=descriptor_id,
            default_width=width_pt,
            w_array=w_array,
        ),
        _font_descriptor_object(
            base_name=base_name,
            stream_id=stream_id,
            bbox=_font_bbox(ttf_data),
        ),
        _font_file_stream_object(data=font_stream),
        _to_unicode_cmap_object(unicode_to_gid),
    )
    return EmbeddedMonoFont(
        pdf_objects=objects,
        resource_name=resource_name,
        units_per_em=units,
        glyph_width=glyph_width,
        unicode_to_gid=unicode_to_gid,
    )


def _font_bbox(ttf_data: bytes) -> tuple[int, int, int, int]:
    font = TTFont(BytesIO(ttf_data))
    head = font["head"]
    return int(head.xMin), int(head.yMin), int(head.xMax), int(head.yMax)


def _build_w_array(unicode_to_gid: dict[int, int], width_pt: int) -> str:
    """PDF ``/W``-Einträge: CID = Glyph-ID → Breite."""
    parts: list[str] = []
    for gid in sorted(set(unicode_to_gid.values())):
        parts.append(f"{gid} [{width_pt}]")
    return " ".join(parts)


def _type0_font_object(*, base_name: str, cid_id: int, to_unicode_id: int) -> bytes:
    return (
        f"<< /Type /Font /Subtype /Type0 /BaseFont /{base_name} "
        f"/Encoding /Identity-H /DescendantFonts [{cid_id} 0 R] "
        f"/ToUnicode {to_unicode_id} 0 R >>"
    ).encode("ascii")


def _cid_font_object(
    *,
    base_name: str,
    descriptor_id: int,
    default_width: int,
    w_array: str,
) -> bytes:
    return (
        f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{base_name} "
        f"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> "
        f"/FontDescriptor {descriptor_id} 0 R /DW {default_width} /W [{w_array}] "
        f"/CIDToGIDMap /Identity >>"
    ).encode("ascii")


def _font_descriptor_object(
    *,
    base_name: str,
    stream_id: int,
    bbox: tuple[int, int, int, int],
) -> bytes:
    x0, y0, x1, y1 = bbox
    return (
        f"<< /Type /FontDescriptor /FontName /{base_name} /Flags 5 "
        f"/FontBBox [{x0} {y0} {x1} {y1}] /ItalicAngle 0 /Ascent {y1} "
        f"/Descent {y0} /CapHeight {y1} /StemV 80 /FontFile2 {stream_id} 0 R >>"
    ).encode("ascii")


def _font_file_stream_object(*, data: bytes) -> bytes:
    return (
        b"<< /Length "
        + str(len(data)).encode("ascii")
        + b" /Filter /FlateDecode >>\nstream\n"
        + data
        + b"\nendstream"
    )


def _to_unicode_cmap_object(unicode_to_gid: dict[int, int]) -> bytes:
    """ToUnicode: CID (Glyph-ID) → Unicode. Druck rendert über CIDToGIDMap."""
    lines = [
        "/CIDInit /ProcSet findresource begin",
        "12 dict begin",
        "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Identity-UCS def",
        "/CMapType 2 def",
        "1 begincodespacerange",
        "<0000> <FFFF>",
        "endcodespacerange",
    ]
    pairs = sorted(unicode_to_gid.items(), key=lambda item: item[1])
    batch_size = 100
    for start in range(0, len(pairs), batch_size):
        batch = pairs[start : start + batch_size]
        lines.append(f"{len(batch)} beginbfchar")
        for code, gid in batch:
            lines.append(f"<{gid:04X}> <{code:04X}>")
        lines.append("endbfchar")
    lines.extend(["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"])
    cmap = "\n".join(lines).encode("ascii")
    return (
        b"<< /Length "
        + str(len(cmap)).encode("ascii")
        + b" >>\nstream\n"
        + cmap
        + b"\nendstream"
    )


def clear_font_cache() -> None:
    """Test-Hilfe: Font-Subset-Cache leeren."""
    _subset_font_bytes.cache_clear()
