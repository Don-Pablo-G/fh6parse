"""Part number and revision from NC programs and STEP file names."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .parser import O_WORD_RE, extract_comments, strip_comments

# Explicit tokens in names: D0134078_Rev03, SE0241282-REV.2, foo_rewizja_1
_EXPLICIT_REV_RE = re.compile(
    r"^(?P<base>.+?)[-_\s]+(?:REV(?:ISION)?|REWIZJA|REW\.?)"
    r"[-_.\s]*(?P<rev>[0-9]{1,3}|[A-Za-z])"
    r"(?:$|(?P<rest>[-_\s].+))$",
    re.IGNORECASE,
)
# D0134078-R02 / D0134078_R2
_R_REV_RE = re.compile(
    r"^(?P<base>.+?)[-_]R(?P<rev>[0-9]{1,3}|[A-Za-z])"
    r"(?:$|(?P<rest>[-_\s].+))$",
    re.IGNORECASE,
)
# Long shop codes with a short trailing rev: SE0241282-0, D0134078-3
_HYPHEN_REV_RE = re.compile(
    r"^(?P<base>[A-Za-z0-9]{6,})-(?P<rev>[0-9]{1,2}|[A-Za-z])"
    r"(?:$|(?P<rest>[-_\s].+))$",
)
# D0134078A.stp — letter glued onto a numeric tail
_GLUED_LETTER_RE = re.compile(
    r"^(?P<base>[A-Za-z]*\d{4,})(?P<rev>[A-Za-z])$"
)

# Header comments: (REV 3), (Rewizja: 02), (REVISION A)
COMMENT_REV_RE = re.compile(
    r"\b(?:REV(?:ISION)?|REWIZJA|REW|WERSJA)\s*[.:]?\s*([0-9]{1,3}|[A-Za-z])\b",
    re.IGNORECASE,
)
T_M6_RE = re.compile(r"\bT\s*\d+\b.*\bM\s*6\b|\bM\s*6\b.*\bT\s*\d+\b", re.IGNORECASE)
GENERIC_STEM_RE = re.compile(r"^O?\d{1,5}$", re.IGNORECASE)


def _alnum_len(text: str) -> int:
    return sum(1 for ch in text if ch.isalnum())


@dataclass(frozen=True)
class Revision:
    """Shop revision: 0/03 or A/B. Numeric 03 equals 3."""

    raw: str
    kind: str  # "num" | "letter"
    number: int | None = None
    letter: str | None = None

    def matches(self, other: Revision | None) -> bool:
        if other is None:
            return False
        if self.kind == "num" and other.kind == "num":
            return self.number == other.number
        return self.kind == other.kind and (self.letter or "") == (other.letter or "")

    def sort_key(self) -> tuple[int, int]:
        if self.kind == "num":
            return (0, self.number or 0)
        return (1, ord(self.letter or "\0"))

    def display(self) -> str:
        if self.kind == "num":
            return str(self.number)
        return self.letter or self.raw


def parse_revision(token: str) -> Revision | None:
    text = (token or "").strip().upper()
    if not text:
        return None
    if re.fullmatch(r"\d{1,3}", text):
        return Revision(raw=text, kind="num", number=int(text))
    if re.fullmatch(r"[A-Z]", text):
        return Revision(raw=text, kind="letter", letter=text)
    return None


@dataclass(frozen=True)
class PartIdentity:
    base: str
    rev: Revision | None = None

    def normalized_base(self) -> str:
        return (self.base or "").upper()


def parse_model_stem(stem: str) -> PartIdentity:
    """Split a file stem or title token into part id + trailing revision."""
    raw = (stem or "").strip()
    if not raw:
        return PartIdentity(base="")
    token = raw.split()[0]
    token = token.replace("/", "-")
    for cre in (_EXPLICIT_REV_RE, _R_REV_RE, _HYPHEN_REV_RE, _GLUED_LETTER_RE):
        m = cre.match(token)
        if not m:
            continue
        base = m.group("base").strip("-_. ")
        rev = parse_revision(m.group("rev"))
        if not base or rev is None:
            continue
        min_base = 6 if cre is _HYPHEN_REV_RE else 4
        if _alnum_len(base) < min_base:
            continue
        return PartIdentity(base=base, rev=rev)
    return PartIdentity(base=token.strip("-_. "))


def _first_o_title(text: str) -> str:
    for raw in text.splitlines()[:80]:
        comments = extract_comments(raw)
        if not comments:
            continue
        if O_WORD_RE.search(strip_comments(raw)):
            return comments[0]
    return ""


def _header_comments(text: str, program_title: str) -> list[str]:
    found: list[str] = []
    for raw in text.splitlines()[:250]:
        code = strip_comments(raw)
        if T_M6_RE.search(code):
            break
        for c in extract_comments(raw):
            if c and c != program_title and c not in found:
                found.append(c)
    return found


def identity_from_nc(*, filename: str, text: str) -> PartIdentity:
    """Part id from the NC file name; revision from G-code, then title, then name."""
    stem = Path(filename).stem
    from_file = parse_model_stem(stem)
    title = _first_o_title(text)
    from_title = parse_model_stem(title) if title else PartIdentity(base="")
    comment_rev: Revision | None = None
    blob = " ".join(_header_comments(text, title))
    if title:
        blob = f"{title} {blob}"
    m = COMMENT_REV_RE.search(blob)
    if m:
        comment_rev = parse_revision(m.group(1))

    base = from_file.base
    if GENERIC_STEM_RE.fullmatch(stem) and from_title.base:
        base = from_title.base
    elif from_title.base and from_file.base:
        ft = from_title.normalized_base()
        ff = from_file.normalized_base()
        if ft.startswith(ff) or ff.startswith(ft):
            base = from_file.base if len(ff) >= len(ft) else from_title.base
    elif from_title.base and not from_file.base:
        base = from_title.base

    rev = comment_rev or from_title.rev or from_file.rev
    return PartIdentity(base=base, rev=rev)


def identity_from_nc_path(path: Path, *, max_bytes: int = 65536) -> PartIdentity:
    data = Path(path).read_bytes()[:max_bytes]
    text = _decode_nc(data)
    return identity_from_nc(filename=Path(path).name, text=text)


def _decode_nc(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1250", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")
