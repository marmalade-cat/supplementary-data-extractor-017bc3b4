supplementary-data-extractor

A tiny Python CLI prototype to find and validate machine-readable supplementary datasets linked from an article URL or DOI. No dependencies; standard library only.

Usage:

python main.py <article-URL-or-DOI>

Output: JSON printed to stdout summarizing found candidate files, download status, and simple structure validation (CSV headers, JSON keys, ZIP-contained files).

Notes:
- This is an untested prototype meant for local use. Network I/O is performed by urllib; respect robots and site terms.
- For DOI input, the script will resolve via https://doi.org/<DOI>.

Limitations:
- HTML link discovery is basic and may miss JS-generated links.
- Validation is lightweight: presence of CSV header row and JSON parse + keys. It does not enforce schema.

License: public domain (owner: marmalade-cat).