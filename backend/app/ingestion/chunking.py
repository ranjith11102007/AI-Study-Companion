"""Text chunking for ingestion.

Splits extracted text into overlapping passages so each stored content unit
is a coherent, independently-embeddable chunk that still preserves order.
"""

import re

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")

# Characters PostgreSQL text columns cannot store (notably NUL, 0x00) plus the
# other non-printable control characters. Tab (\x09) and newline (\x0a) are kept
# on purpose because chunking relies on them.
_DISALLOWED_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(text: str | None) -> str:
    """Remove characters a PostgreSQL text column rejects.

    PDF text extraction can emit NUL (``0x00``) or stray control characters.
    Postgres raises ``CharacterNotInRepertoireError`` for those, which used to
    mark a whole upload as *failed*; stripping them here keeps the source
    indexable. Line endings are normalised to ``\\n``.
    """
    if not text:
        return ""
    cleaned = _DISALLOWED_CONTROL.sub("", text)
    return cleaned.replace("\r\n", "\n").replace("\r", "\n")


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    """Split ``text`` into chunks of at most ``size`` chars with ``overlap``.

    Paragraph boundaries are respected where possible; a single oversized
    paragraph is hard-split so no chunk exceeds ``size`` characters.
    """
    text = sanitize_text(text).strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    size = max(size, 1)
    overlap = max(min(overlap, size - 1), 0)

    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    grouped: list[str] = []
    buffer = ""
    for para in paragraphs:
        if not buffer:
            buffer = para
        elif len(buffer) + 2 + len(para) <= size:
            buffer = f"{buffer}\n\n{para}"
        else:
            grouped.append(buffer)
            tail = buffer[-overlap:] if overlap else ""
            buffer = f"{tail}\n\n{para}".strip() if tail else para
    if buffer:
        grouped.append(buffer)

    chunks: list[str] = []
    for block in grouped:
        if len(block) <= size:
            chunks.append(block)
            continue
        start = 0
        step = size - overlap
        while start < len(block):
            chunks.append(block[start : start + size])
            start += step

    return [c.strip() for c in chunks if c.strip()]
