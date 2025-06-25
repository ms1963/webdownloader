# WebDownload

A console-based Python tool to search the web for documents on a given subject and download them locally. Supports concurrent downloads, retries with exponential back-off, and optional file-type filtering.

## Features

- **Search**: Scrapes DuckDuckGo HTML results and the results of other search engines (Bing, Google) avoiding API rate limits.
- **Download**: Streams files and inspects MIME type (via `python-magic`) to ensure only supported types are saved.
- **File Types**: PDF, Word (DOC/DOCX), Markdown, HTML, Plain text.
- **Concurrency**: Parallel downloads with configurable number of worker threads.
- **Retries**: Per-file retry logic with exponential back-off on network or I/O errors.
- **Filtering**: Optional `--only` flag to limit downloaded file-types (e.g. `--only pdf,docx,md`).
- **Flexible**: Specify maximum number of documents, custom output directory, etc.

## Prerequisites

- Python 3.7+
- **pip** packages:
  - `requests`
  - `beautifulsoup4`
  - `python-magic` (on Linux, you may need to install the system `libmagic` / `file` package)

```bash
pip install requests beautifulsoup4 python-magic

## Installation

Clone or download this repository, then ensure dependencies are installed:

git clone https://github.com/ms1963/webdownloader.git
cd webdownload
pip install -r requirements.txt
	
(Alternatively, install dependencies manually as shown above.)

### Usage

python wd.py -s SUBJECT [OPTIONS]

Required
• -s, --subject
Search subject (e.g. "quantum computing").

Optional
• -d, --destination
Output directory. Default: downloads_<YYYYMMDD_HHMMSS>_<uuid>.
• -m, --max
Maximum documents to download. Default: 5.
• -w, --workers
Number of concurrent download threads. Default: 5.
• -o, --only
Comma-separated list of extensions to download.
Supported: pdf, doc, docx, md, markdown, html, htm, txt.
• -h, --help
Show help message and exit.

python wd.py --help

How to use the new --engine flag
# Default (DuckDuckGo scraping)
wd -s "Quantum Computing"

# Use Bing instead
wd -s "Quantum Computing" -e bing

# Use Google (may be blocked by Google if scraped too often)
wd -s "Quantum Computing" -e google

# Combine with other flags
wd -s "AI survey" -e bing -m 10 -w 8 -o pdf,docx


## Examples
• Default download (5 files of all supported types):
python wd.py -s "machine learning"

• Specify max and concurrency:
python wd.py -s "AI ethics" -m 10 -w 8

• Download only PDFs and Word docs:
python wd.py -s "blockchain survey" -o pdf,docx


• Custom output directory:
python wd.py -s "covid-19 research" -d ./covid_docs

## How It Works
1. Search
Sends a POST to https://html.duckduckgo.com/html/ and parses result links via BeautifulSoup.
2. Filter & Download
 • Builds a query that includes only the desired filetype: filters.
 • Streams each URL, writes to a temporary .part file.
 • Uses python-magic to detect MIME and confirm it matches one of the allowed types.
 • Renames and keeps only valid files.
3. Concurrency & Retries
 • Submits downloads to a ThreadPoolExecutor.
 • On network or I/O errors, retries up to 3 times with exponential back-off (1s, 2s, 4s).

## License

MIT © Michael Stal




	
		
