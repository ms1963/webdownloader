#!/usr/bin/env python3
"""
webdownload.py

Search and download documents on a given subject by per-extension
filetype: queries, with engine fallback, UA rotation, and inter-query delays
to avoid rate-limiting.
"""
import argparse
import sys
import uuid
import datetime
import logging
import time
import random
from pathlib import Path
from urllib.parse import urlparse

import requests
import magic  # python-magic
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# Supported extensions → MIME
ALL_EXTENSIONS = {
    '.pdf':     'application/pdf',
    '.doc':     'application/msword',
    '.docx':    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.md':      'text/markdown',
    '.markdown':'text/markdown',
    '.html':    'text/html',
    '.htm':     'text/html',
    '.txt':     'text/plain',
}

# Pause between search requests (seconds)
SEARCH_PAUSE = 2

# A small pool of realistic User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/114.0 Safari/537.36",
]

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def random_headers():
    return {'User-Agent': random.choice(USER_AGENTS)}


class SearchEngine:
    def search(self, query: str, max_results: int):
        raise NotImplementedError

    def _get_with_retry(self, url, params, max_attempts=3):
        delay = 1
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.get(url, params=params, headers=random_headers(), timeout=15)
                # If being rate-limited, status code 429
                if resp.status_code == 429:
                    raise requests.HTTPError("429 Rate Limited")
                resp.raise_for_status()
                return resp
            except requests.HTTPError as e:
                logging.warning(f"Search HTTP error (attempt {attempt}): {e}")
            except requests.RequestException as e:
                logging.warning(f"Search request failed (attempt {attempt}): {e}")
            if attempt < max_attempts:
                time.sleep(delay)
                delay *= 2
        logging.error(f"Failed to GET {url} after {max_attempts} attempts")
        return None


class DuckDuckGoEngine(SearchEngine):
    BASE = "https://html.duckduckgo.com/html/"

    def search(self, query: str, max_results: int):
        resp = self._get_with_retry(self.BASE, {'q': query})
        if not resp:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        results = []
        for a in soup.select('a.result__a[href]'):
            href = a['href']
            if href.startswith('/l/?'):
                for part in href[3:].split('&'):
                    if part.startswith('uddg='):
                        href = requests.utils.unquote(part.split('=',1)[1])
                        break
            results.append(href)
            if len(results) >= max_results:
                break
        return results


class BingEngine(SearchEngine):
    BASE = "https://www.bing.com/search"

    def search(self, query: str, max_results: int):
        resp = self._get_with_retry(self.BASE, {'q': query})
        if not resp:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        return [a['href'] for a in soup.select('li.b_algo h2 a[href]')][:max_results]


class GoogleEngine(SearchEngine):
    BASE = "https://www.google.com/search"

    def search(self, query: str, max_results: int):
        resp = self._get_with_retry(self.BASE, {'q': query, 'num': max_results})
        if not resp:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = []
        for g in soup.select('div.g'):
            a = g.find('a', href=True)
            if a and not a['href'].startswith('/'):
                links.append(a['href'])
            if len(links) >= max_results:
                break
        return links


ENGINES = {
    'duckduckgo': DuckDuckGoEngine(),
    'bing':       BingEngine(),
    'google':     GoogleEngine(),
}


def sanitize_filename(name: str) -> str:
    keep = (' ', '.', '_', '-')
    return "".join(c for c in name if c.isalnum() or c in keep).rstrip()


def parse_only(arg: str):
    exts = {}
    for tok in arg.split(','):
        tok = tok.strip().lower().lstrip('.')
        key = f".{tok}"
        if key not in ALL_EXTENSIONS:
            raise ValueError(f"Unsupported extension: {tok}")
        exts[key] = ALL_EXTENSIONS[key]
    return exts


def download_file(url: str, dest: Path, allowed: dict) -> bool:
    r = requests.get(url, stream=True, timeout=15, headers=random_headers())
    r.raise_for_status()
    tmp = dest.with_suffix(dest.suffix + '.part')
    with open(tmp, 'wb') as f:
        for chunk in r.iter_content(4096):
            f.write(chunk)
    mime = magic.from_file(str(tmp), mime=True)
    ext = dest.suffix.lower()
    if ext in allowed:
        if not mime.startswith(allowed[ext].split('/')[0]):
            logging.info(f"Skipping {url}: MIME {mime} ≠ {allowed[ext]}")
            tmp.unlink(missing_ok=True)
            return False
    else:
        for e, m in allowed.items():
            if mime == m:
                dest = dest.with_suffix(e)
                break
        else:
            logging.info(f"Skipping {url}: unsupported MIME {mime}")
            tmp.unlink(missing_ok=True)
            return False
    tmp.rename(dest)
    logging.info(f"Saved: {dest.name} ({mime})")
    return True


def download_with_retry(url: str, outdir: Path, allowed: dict, attempts: int = 3) -> bool:
    name = sanitize_filename(Path(url).stem) or uuid.uuid4().hex
    ext = Path(urlparse(url).path).suffix.lower()
    dest = outdir / name
    if ext in allowed:
        dest = dest.with_suffix(ext)
    delay = 1
    for i in range(1, attempts + 1):
        try:
            return download_file(url, dest, allowed)
        except (requests.RequestException, OSError) as e:
            logging.warning(f"[{url}] attempt {i}/{attempts} failed: {e}")
            if i < attempts:
                time.sleep(delay)
                delay *= 2
            else:
                logging.error(f"[{url}] giving up.")
                return False


def main():
    p = argparse.ArgumentParser(
        description="Search+download documents via per-extension filetype: queries\n"
                    "with engine fallback, UA rotation, and inter-query delays.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Examples:\n"
               "  webdownload -s \"quantum computing\"\n"
               "  webdownload -s \"AI\" -m 10 -w 8 -o pdf,docx\n"
               "  webdownload -s \"ML\" -e bing\n"
    )
    p.add_argument('-s','--subject',    required=True, help='Search subject text')
    p.add_argument('-d','--destination', help='Output directory')
    p.add_argument('-m','--max',        type=int, default=5, help='Max docs to download')
    p.add_argument('-w','--workers',    type=int, default=5, help='Concurrent downloads')
    p.add_argument('-o','--only',       help='Comma list of extensions: pdf,docx,md,...')
    p.add_argument('-e','--engine',     choices=ENGINES, default='duckduckgo',
                   help='Primary search engine')
    args = p.parse_args()

    allowed = ALL_EXTENSIONS if not args.only else parse_only(args.only)

    # prepare output dir
    if args.destination:
        outdir = Path(args.destination)
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:6]
        outdir = Path(f"downloads_{ts}_{uid}")
    outdir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Saving files to {outdir.resolve()}")

    # search loop with fallback
    primary = args.engine
    ordered = [primary] + [e for e in ENGINES if e != primary]
    doc_urls = []

    for ext in allowed:
        if len(doc_urls) >= args.max:
            break
        suffix = ext.lstrip('.')
        query = f"{args.subject} filetype:{suffix}"
        for name in ordered:
            engine = ENGINES[name]
            logging.info(f"[{ext}] searching with {name}: {query!r}")
            results = engine.search(query, max_results=args.max)
            if results:
                for u in results:
                    if u.lower().endswith(ext) and u not in doc_urls:
                        doc_urls.append(u)
                        if len(doc_urls) >= args.max:
                            break
                break
            # pause before trying next engine
            time.sleep(SEARCH_PAUSE)

    if not doc_urls:
        logging.error("No document URLs found via any engine.")
        sys.exit(1)

    # download concurrently
    downloaded = 0
    with ThreadPoolExecutor(max_workers=args.workers) as exe:
        futures = [exe.submit(download_with_retry, u, outdir, allowed) for u in doc_urls]
        for f in as_completed(futures):
            if f.result():
                downloaded += 1

    logging.info(f"Done: {downloaded}/{len(doc_urls)} file(s) downloaded.")


if __name__ == "__main__":
    main()
