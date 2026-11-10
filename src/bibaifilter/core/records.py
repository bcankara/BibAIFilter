"""Reading bibliographic records and normalising them to one schema.

Supported inputs: Excel (.xlsx, .xls), CSV/TSV (including Scopus CSV exports),
RIS (.ris), BibTeX (.bib) and Web of Science plain-text exports (.txt, tagged
``TI``/``AB``/``DE``...). Every record gets a stable ``rid`` (its position in the
input file) and a content hash, so that a run can be traced back to the exact
text that was sent.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

# Column-name synonyms used to guess the mapping of a tabular file.
# Compared case-insensitively after stripping non-alphanumerics.
COLUMN_SYNONYMS: dict[str, list[str]] = {
    "title": ["title", "articletitle", "documenttitle", "ti", "papertitle"],
    "abstract": ["abstract", "ab", "summary", "description"],
    "keywords": ["authorkeywords", "keywords", "de", "keyword", "kw", "indexkeywords", "keywordsplus", "id"],
    "year": ["year", "py", "publicationyear", "pubyear"],
    "doi": ["doi", "di"],
    "authors": ["authors", "author", "au", "authorfullnames", "af"],
    "source": ["sourcetitle", "source", "journal", "so", "publicationtitle", "t2", "jo"],
    "categories": ["webofsciencecategories", "wc", "subjectarea", "categories", "sc", "researchareas"],
    "label": ["label", "labelincluded", "included", "include", "decision", "goldlabel", "relevant"],
    "reference_score": ["humanscore", "referencescore", "humanmean", "meanrating", "goldscore"],
}

FIELDS = ["title", "abstract", "keywords", "year", "doi", "authors", "source", "categories"]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


@dataclass
class Record:
    rid: int
    title: str = ""
    abstract: str = ""
    keywords: str = ""
    year: str = ""
    doi: str = ""
    authors: str = ""
    source: str = ""
    categories: str = ""
    label: Optional[int] = None  # 1 = include, 0 = exclude, None = unknown
    reference_score: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def text_hash(self) -> str:
        """SHA-256 of the fields that can enter a prompt (12 hex chars)."""
        payload = "\x1f".join([self.title, self.abstract, self.keywords, self.categories])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    @property
    def is_empty(self) -> bool:
        return not self.title.strip() and not self.abstract.strip()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["text_hash"] = self.text_hash
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Record":
        d = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**d)


# ---------------------------------------------------------------------------
# Value cleaning


def _clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


_TRUE = {"1", "yes", "y", "true", "include", "included", "relevant", "i", "evet"}
_FALSE = {"0", "no", "n", "false", "exclude", "excluded", "irrelevant", "e", "hayir", "hayır"}


def parse_label(value: Any) -> Optional[int]:
    s = _clean(value).lower()
    if not s:
        return None
    if s in _TRUE:
        return 1
    if s in _FALSE:
        return 0
    return None


def _to_float(value: Any) -> Optional[float]:
    s = _clean(value).replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Tabular files


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return pd.read_excel(path, engine="openpyxl", dtype=object)
    if suffix == ".xls":
        return pd.read_excel(path, engine="xlrd", dtype=object)
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    assert text is not None
    try:
        dialect = csv.Sniffer().sniff(text[:20000], delimiters=",;\t")
        sep = dialect.delimiter
    except csv.Error:
        sep = "\t" if suffix in (".tsv", ".tab") else ","
    return pd.read_csv(io.StringIO(text), sep=sep, dtype=object, keep_default_na=False)


def guess_mapping(columns: Iterable[str]) -> dict[str, Optional[str]]:
    """Map our fields to the best-matching column names (or None)."""
    cols = list(columns)
    normed = {_norm(c): c for c in cols}
    mapping: dict[str, Optional[str]] = {}
    used: set[str] = set()
    for fld, synonyms in COLUMN_SYNONYMS.items():
        mapping[fld] = None
        for syn in synonyms:
            col = normed.get(syn)
            if col is not None and col not in used:
                mapping[fld] = col
                used.add(col)
                break
    return mapping


def records_from_frame(df: pd.DataFrame, mapping: dict[str, Optional[str]]) -> list[Record]:
    records: list[Record] = []
    for i, row in enumerate(df.to_dict(orient="records")):
        kw: dict[str, Any] = {}
        for fld in FIELDS:
            col = mapping.get(fld)
            kw[fld] = _clean(row.get(col)) if col else ""
        label_col = mapping.get("label")
        ref_col = mapping.get("reference_score")
        rec = Record(
            rid=i,
            label=parse_label(row.get(label_col)) if label_col else None,
            reference_score=_to_float(row.get(ref_col)) if ref_col else None,
            **kw,
        )
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Tagged formats (RIS, Web of Science)

_RIS_LINE = re.compile(r"^([A-Z][A-Z0-9])  - ?(.*)$")
_RIS_MAP = {
    "TI": "title", "T1": "title", "AB": "abstract", "N2": "abstract", "KW": "keywords",
    "PY": "year", "Y1": "year", "DO": "doi", "AU": "authors", "A1": "authors",
    "T2": "source", "JO": "source", "JF": "source",
}


def parse_ris(text: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    cur: dict[str, list[str]] = {}
    for line in text.splitlines():
        m = _RIS_LINE.match(line.rstrip())
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "ER":
            if cur:
                rows.append({k: "; ".join(v) for k, v in cur.items()})
            cur = {}
            continue
        fld = _RIS_MAP.get(tag)
        if fld:
            if fld == "year":
                val = val[:4]
            cur.setdefault(fld, []).append(val)
    if cur:
        rows.append({k: "; ".join(v) for k, v in cur.items()})
    return pd.DataFrame(rows, columns=FIELDS, dtype=object).fillna("")


_WOS_MAP = {"TI": "title", "AB": "abstract", "DE": "keywords", "PY": "year", "DI": "doi",
            "AU": "authors", "SO": "source", "WC": "categories"}


def parse_wos(text: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    cur: dict[str, list[str]] = {}
    tag: Optional[str] = None
    for line in text.splitlines():
        if line.startswith("ER"):
            if cur:
                rows.append({k: " ".join(v) if k != "authors" else "; ".join(v) for k, v in cur.items()})
            cur, tag = {}, None
            continue
        if len(line) >= 3 and line[:2].strip() and line[2] == " ":
            tag = line[:2]
            val = line[3:].strip()
        elif line.startswith("   ") and tag:
            val = line.strip()
        else:
            continue
        fld = _WOS_MAP.get(tag or "")
        if fld:
            cur.setdefault(fld, []).append(val)
    return pd.DataFrame(rows, columns=FIELDS, dtype=object).fillna("")


def parse_bibtex(text: str) -> pd.DataFrame:
    """Small BibTeX reader: handles ``field = {...}`` and ``field = "..."`` with nested braces."""
    rows: list[dict[str, str]] = []
    for entry in re.split(r"\n\s*@", "\n" + text)[1:]:
        fields: dict[str, str] = {}
        i = entry.find(",")
        body = entry[i + 1:] if i >= 0 else ""
        pos = 0
        while True:
            m = re.compile(r"\s*([A-Za-z_\-]+)\s*=\s*").match(body, pos)
            if not m:
                break
            name = m.group(1).lower()
            pos = m.end()
            if pos >= len(body):
                break
            if body[pos] == "{":
                depth, start = 0, pos
                while pos < len(body):
                    if body[pos] == "{":
                        depth += 1
                    elif body[pos] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    pos += 1
                value = body[start + 1:pos]
                pos += 1
            elif body[pos] == '"':
                end = body.find('"', pos + 1)
                value = body[pos + 1:end]
                pos = end + 1
            else:
                m2 = re.compile(r"[^,\n}]*").match(body, pos)
                value = m2.group(0) if m2 else ""
                pos = m2.end() if m2 else pos
            fields[name] = re.sub(r"\s+", " ", value.replace("{", "").replace("}", "")).strip()
            comma = body.find(",", pos)
            if comma < 0:
                break
            pos = comma + 1
        rows.append({
            "title": fields.get("title", ""), "abstract": fields.get("abstract", ""),
            "keywords": fields.get("keywords", fields.get("author_keywords", "")),
            "year": fields.get("year", ""), "doi": fields.get("doi", ""),
            "authors": fields.get("author", ""),
            "source": fields.get("journal", fields.get("booktitle", "")),
            "categories": fields.get("web-of-science-categories", ""),
        })
    return pd.DataFrame(rows, columns=FIELDS, dtype=object).fillna("")


def load_any(path: Path) -> tuple[pd.DataFrame, dict[str, Optional[str]], str]:
    """Load a file; return (frame, guessed mapping, detected format)."""
    suffix = path.suffix.lower()
    if suffix in (".ris",):
        df = parse_ris(path.read_text(encoding="utf-8-sig", errors="replace"))
        return df, {f: f for f in FIELDS} | {"label": None, "reference_score": None}, "ris"
    if suffix in (".bib", ".bibtex"):
        df = parse_bibtex(path.read_text(encoding="utf-8-sig", errors="replace"))
        return df, {f: f for f in FIELDS} | {"label": None, "reference_score": None}, "bibtex"
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if re.search(r"^PT [A-Z]", text, re.M) or text.startswith("FN "):
            df = parse_wos(text)
            return df, {f: f for f in FIELDS} | {"label": None, "reference_score": None}, "wos"
        if re.search(r"^TY  - ", text, re.M):
            df = parse_ris(text)
            return df, {f: f for f in FIELDS} | {"label": None, "reference_score": None}, "ris"
    df = read_table(path)
    df.columns = [str(c) for c in df.columns]
    return df, guess_mapping(df.columns), "table"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
