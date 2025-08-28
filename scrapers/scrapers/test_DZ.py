#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, io, json, re, sys
from datetime import datetime, date
from urllib.parse import urljoin

import httpx
import pdfplumber
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
SCRAPER_API_KEY = (os.getenv("SCRAPER_API_KEY") or "").strip()
SCRAPER_DEBUG   = os.getenv("SCRAPER_DEBUG", "0") in ("1", "true", "True", "yes", "YES")
SCRAPER_LOG_FILE = os.getenv("SCRAPER_LOG_FILE", "").strip()  # e.g. /tmp/test_algerie.log

TARGET_URL   = "https://www.bank-of-algeria.dz/taux-de-change-journalier/"
HEADERS      = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
HTML_TIMEOUT = httpx.Timeout(connect=20.0, read=20.0, write=20.0, pool=5.0)
PDF_TIMEOUT  = httpx.Timeout(connect=10.0,  read=20.0, write=10.0, pool=5.0)

PDF_PATTERN  = re.compile(r"/stoodroa/\d{4}/\d{2}/cotation-\d+\.pdf$", re.I)
FLOAT_RE     = r"[0-9]{1,3}(?:[ \u202f]?[0-9]{3})*(?:[.,][0-9]+)?"
FR_MONTHS = {
    "janvier":1,"février":2,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
    "juillet":7,"août":8,"aout":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12,"decembre":12
}

# --------- Debug helpers (stderr/file; never stdout) ----------
def _dbg(stage: str, msg: str):
    if not SCRAPER_DEBUG:
        return
    line = f"[ALGERIE_SCRAPER] {stage}: {msg}\n"
    try:
        sys.stderr.write(line)
    except Exception:
        pass
    if SCRAPER_LOG_FILE:
        try:
            with open(SCRAPER_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

def _today_iso() -> str:
    return date.today().isoformat()

def _to_float(s: str) -> float:
    return float(s.replace("\u202f","").replace(" ","").replace(",", "."))

def _parse_fr_date(s: str):
    m = re.search(r"(\d{1,2})\s+([A-Za-zéèêëàâîïôöûüç]+)\s+(\d{4})", s, re.I)
    if not m: return None
    d, mois, y = m.groups()
    mnum = FR_MONTHS.get(mois.lower())
    if not mnum: return None
    return f"{y}-{mnum:02d}-{int(d):02d}"

# ---------- Schema validator ----------
REQUIRED_KEYS = ("date_publication","nom_brut","code_iso","unite","valeur")
def _validate_rows(rows):
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list")
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            raise ValueError(f"Row {i} is not a dict")
        for k in REQUIRED_KEYS:
            if k not in r:
                raise ValueError(f"Row {i} missing key: {k}")
        # basic types
        if not isinstance(r["date_publication"], str):
            raise ValueError(f"Row {i} date_publication must be str")
        if not isinstance(r["nom_brut"], str) or not isinstance(r["code_iso"], str):
            raise ValueError(f"Row {i} nom_brut/code_iso must be str")
        if not isinstance(r["unite"], int):
            raise ValueError(f"Row {i} unite must be int")
        if not (isinstance(r["valeur"], int) or isinstance(r["valeur"], float)):
            raise ValueError(f"Row {i} valeur must be number")

# ---------- HTML path ----------
def _fetch_html() -> str:
    if not SCRAPER_API_KEY:
        raise RuntimeError("SCRAPER_API_KEY missing")
    params = {"api_key": SCRAPER_API_KEY, "url": TARGET_URL, "render": "true", "wait_for_selector": "table"}
    _dbg("HTML_FETCH", f"GET ScraperAPI with wait_for_selector; url={TARGET_URL}")
    with httpx.Client(timeout=HTML_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        r = client.get("https://api.scraperapi.com", params=params)
        try:
            r.raise_for_status()
            return r.text
        except httpx.HTTPStatusError as e:
            _dbg("HTML_FETCH", f"retry without wait_for_selector due to {e}")
            params.pop("wait_for_selector", None)
            r2 = client.get("https://api.scraperapi.com", params=params)
            r2.raise_for_status()
            return r2.text

def _parse_html_rows(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table")
    if not table:
        raise RuntimeError("table not found")
    headers = table.select("th")
    latest_col_index = None
    date_raw = None
    for idx, th in enumerate(headers):
        txt = th.get_text(strip=True)
        if re.match(r"\d{2}-\d{2}-\d{4}", txt):
            date_raw = txt
            latest_col_index = idx
            break
    if latest_col_index is None:
        raise RuntimeError("date column not found in header")

    try:
        date_publication = datetime.strptime(date_raw, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        date_publication = _today_iso()

    out = []
    for row in table.select("tr")[1:]:
        cols = row.select("td")
        if len(cols) <= latest_col_index or not cols:
            continue
        code = cols[0].get_text(strip=True).upper()
        if not code:
            continue
        try:
            valeur = float(cols[latest_col_index].get_text(strip=True).replace(",", "."))
        except Exception:
            continue
        out.append({
            "date_publication": date_publication,
            "nom_brut": code,
            "code_iso": code,
            "unite": 1,
            "valeur": valeur
        })
    if not out:
        raise RuntimeError("no usable rows in HTML")
    return out

# ---------- PDF path ----------
def _get_latest_pdf_url() -> str:
    _dbg("PDF_URL", "discovering latest PDF link")
    with httpx.Client(follow_redirects=True, headers=HEADERS, timeout=PDF_TIMEOUT) as client:
        r = client.get(TARGET_URL); r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if PDF_PATTERN.search(href):
                url = urljoin(TARGET_URL, href)
                _dbg("PDF_URL", f"found: {url}")
                return url
    raise RuntimeError("no PDF link found")

def _download_pdf(url: str) -> bytes:
    _dbg("PDF_DL", f"downloading {url}")
    with httpx.Client(follow_redirects=True, headers=HEADERS, timeout=PDF_TIMEOUT) as client:
        r = client.get(url); r.raise_for_status()
        return r.content

def _parse_pdf_dates(pdf_bytes: bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page0 = pdf.pages[0]
        txt = page0.extract_text() or ""
        m1 = re.search(r"Cours du\s*:\s*(.+)", txt, re.I)
        m2 = re.search(r"Valeur\s*:\s*(.+)", txt, re.I)
        cours_du = _parse_fr_date(m1.group(1)) if m1 else None
        valeur   = _parse_fr_date(m2.group(1)) if m2 else None
        return cours_du, valeur

def _parse_pdf_lines(pdf_bytes: bytes) -> list[dict]:
    _dbg("PDF_PARSE", "extracting tables/lines")
    results = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            try:
                tables = page.extract_tables(table_settings={
                    "vertical_strategy":"lines","horizontal_strategy":"lines",
                    "intersection_tolerance":6,"edge_min_length":18,
                    "snap_tolerance":3,"join_tolerance":3,"text_tolerance":3
                }) or []
            except TypeError:
                tables = page.extract_tables() or []

            lines = []
            for t in tables:
                for row in t:
                    if not row: continue
                    cells = [(c or "").strip() for c in row]
                    if "".join(cells).strip() == "": continue
                    lines.append("  ".join(cells))

            if not lines:
                txt = page.extract_text() or ""
                lines += [l.strip() for l in txt.splitlines() if l.strip()]

            for line in lines:
                U = line.upper()
                if "COURS ACHAT" in U or "COURS VENTE" in U or ("BASE" in U and "DEVISES" in U):
                    continue
                nums = list(re.finditer(FLOAT_RE, line))
                if len(nums) < 2:
                    continue
                achat_s = nums[-2].group(0); vente_s = nums[-1].group(0)
                m_base = re.search(r"\b(\d{1,3})\b", line)
                base = m_base.group(1) if m_base else "1"
                m_code = re.search(r"\b([A-Z]{3,4})\b", line)
                if not m_code: 
                    continue
                code = m_code.group(1).upper()
                start_dev = m_code.end(); end_dev = nums[-2].start()
                devise = re.sub(r"\s{2,}", " ", line[start_dev:end_dev]).strip(" -|\t\u00a0")
                try:
                    achat = _to_float(achat_s); vente = _to_float(vente_s)
                except Exception:
                    continue
                if achat <= 0 or vente <= 0:
                    continue
                results.append({"base": base, "code": code, "devise": devise, "achat": achat, "vente": vente})
    # dedup
    dedup = {}
    for r in results:
        dedup[(r["code"], r["achat"], r["vente"])] = r
    return list(dedup.values())

def _pdf_to_rows(pdf_bytes: bytes) -> list[dict]:
    cours_du, valeur_du = _parse_pdf_dates(pdf_bytes)
    date_publication = cours_du or valeur_du or _today_iso()
    raw = _parse_pdf_lines(pdf_bytes)
    out = []
    for r in raw:
        out.append({
            "date_publication": date_publication,
            "nom_brut": r.get("devise") or r["code"],
            "code_iso": r["code"],
            "unite": int(r.get("base") or 1),
            "valeur": float(r["achat"])  # switch to r["vente"] or avg if wanted
        })
    return out

# ---------- Orchestrator ----------
def run() -> list[dict]:
    try:
        if SCRAPER_API_KEY:
            _dbg("HTML_FETCH", "starting")
            html = _fetch_html()
            _dbg("HTML_PARSE", "parsing")
            rows = _parse_html_rows(html)
            _dbg("HTML_PARSE", f"rows={len(rows)}")
            _validate_rows(rows)
            _dbg("RETURN", "HTML path OK")
            return rows
        else:
            _dbg("HTML_FETCH", "skipped (no API key)")
    except Exception as e:
        _dbg("HTML_ERROR", repr(e))

    try:
        pdf_url = _get_latest_pdf_url()
        pdf_bytes = _download_pdf(pdf_url)
        rows = _pdf_to_rows(pdf_bytes)
        _dbg("PDF_TO_ROWS", f"rows={len(rows)}")
        _validate_rows(rows)
        _dbg("RETURN", "PDF path OK")
        return rows
    except Exception as e:
        _dbg("PDF_ERROR", repr(e))
        return []

if __name__ == "__main__":
    # Only print JSON to stdout.
    print(json.dumps(run(), ensure_ascii=False))
