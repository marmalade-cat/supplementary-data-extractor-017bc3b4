#!/usr/bin/env python3
"""
Prototype CLI for locating and validating supplementary data files (CSV, JSON, ZIP) linked from an article URL or DOI.
Uses Python 3 standard library only.
"""
import sys
import urllib.request
import urllib.parse
import json
import io
import csv
import zipfile
from html.parser import HTMLParser

class LinkParser(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.links = []
        self.base = base
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            href = None
            for k,v in attrs:
                if k.lower() == 'href':
                    href = v
            if href:
                full = urllib.parse.urljoin(self.base, href)
                self.links.append(full)

def fetch_url(url):
    req = urllib.request.Request(url, headers={'User-Agent':'supplementary-data-extractor/0.1'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read(), resp.getheader('Content-Type')

def is_candidate_url(url):
    lower = url.lower()
    for ext in ('.csv','.json','.zip'):
        if lower.endswith(ext):
            return True
    # also consider links that include 'supplement' or 'fig' or 'data'
    if any(p in lower for p in ('supplement','supplementary','supp','data','dataset','fig')):
        return True
    return False

def validate_csv_bytes(b):
    try:
        s = b.decode('utf-8')
    except Exception:
        try:
            s = b.decode('latin-1')
        except Exception:
            return {'ok':False,'reason':'decode_error'}
    f = io.StringIO(s)
    try:
        reader = csv.reader(f)
        rows = [r for _,r in zip(range(5), reader)]
        if not rows:
            return {'ok':False,'reason':'empty'}
        header = rows[0]
        if all(not h.strip() for h in header):
            return {'ok':False,'reason':'no_header'}
        return {'ok':True,'header':header}
    except Exception as e:
        return {'ok':False,'reason':'csv_parse_error','error':str(e)}

def validate_json_bytes(b):
    try:
        obj = json.loads(b.decode('utf-8'))
    except Exception:
        try:
            obj = json.loads(b.decode('latin-1'))
        except Exception as e:
            return {'ok':False,'reason':'json_parse_error','error':str(e)}
    if isinstance(obj, dict):
        keys = list(obj.keys())
        return {'ok':True,'type':'object','keys_sample':keys[:10]}
    if isinstance(obj, list):
        sample = obj[:5]
        if sample and isinstance(sample[0], dict):
            keys = list(sample[0].keys())
            return {'ok':True,'type':'array','item_keys_sample':keys[:10]}
        return {'ok':True,'type':'array','item_sample_count':len(sample)}
    return {'ok':True,'type':type(obj).__name__}

def inspect_zip_bytes(b):
    res = []
    try:
        z = zipfile.ZipFile(io.BytesIO(b))
    except Exception as e:
        return {'ok':False,'reason':'not_zip','error':str(e)}
    for name in z.namelist():
        lower = name.lower()
        entry = {'name':name}
        try:
            with z.open(name) as f:
                data = f.read(200000)  # limit
            if lower.endswith('.csv'):
                entry['type']='csv'
                entry['validation']=validate_csv_bytes(data)
            elif lower.endswith('.json'):
                entry['type']='json'
                entry['validation']=validate_json_bytes(data)
            else:
                entry['type']='other'
                entry['size']=len(data)
        except Exception as e:
            entry['error']=str(e)
        res.append(entry)
    return {'ok':True,'members':res}

def download_and_validate(url):
    out = {'url':url}
    try:
        data, ctype = fetch_url(url)
        out['fetched']=True
        out['content_type']=ctype
        lower = url.lower()
        if lower.endswith('.csv') or (ctype and 'text/csv' in (ctype or '')):
            out['format']='csv'
            out['validation']=validate_csv_bytes(data)
        elif lower.endswith('.json') or (ctype and 'application/json' in (ctype or '')):
            out['format']='json'
            out['validation']=validate_json_bytes(data)
        elif lower.endswith('.zip') or (ctype and 'zip' in (ctype or '')):
            out['format']='zip'
            out['validation']=inspect_zip_bytes(data)
        else:
            # try to sniff
            sample = data[:200].lstrip()
            if sample.startswith(b'{') or sample.startswith(b'['):
                out['format']='json'
                out['validation']=validate_json_bytes(data)
            elif b',' in sample or b'\n' in sample:
                out['format']='csv'
                out['validation']=validate_csv_bytes(data)
            else:
                out['format']='unknown'
                out['size']=len(data)
    except Exception as e:
        out['fetched']=False
        out['error']=str(e)
    return out

def gather_candidates(root_url):
    try:
        body,ctype = fetch_url(root_url)
    except Exception as e:
        return {'error':'fetch_root_failed','detail':str(e)}
    try:
        text = body.decode('utf-8', errors='ignore')
    except Exception:
        text = body.decode('latin-1', errors='ignore')
    parser = LinkParser(root_url)
    parser.feed(text)
    links = parser.links
    # prefer links that look like supplemental or direct file links
    candidates = []
    for l in links:
        if is_candidate_url(l):
            candidates.append(l)
    # dedupe while preserving order
    seen = set()
    uniq = []
    for l in candidates:
        if l not in seen:
            seen.add(l); uniq.append(l)
    return {'root':root_url,'candidates':uniq,'all_links_count':len(links)}

def resolve_input(arg):
    # naive DOI detection: contains '/' and no scheme but pattern like 10.x/
    if arg.startswith('http://') or arg.startswith('https://'):
        return arg
    if arg.startswith('10.') or '/10.' in arg:
        # treat as DOI
        doi = arg
        if doi.startswith('doi:'):
            doi = doi.split(':',1)[1]
        return 'https://doi.org/' + doi
    # otherwise assume URL missing scheme
    return 'https://' + arg

def main():
    if len(sys.argv)<2:
        print('Usage: python main.py <article-URL-or-DOI>')
        sys.exit(1)
    inp = sys.argv[1]
    start = resolve_input(inp)
    summary = {'input':inp,'resolved':start}
    gathered = gather_candidates(start)
    summary['gather']=gathered
    candidates = gathered.get('candidates', []) if isinstance(gathered, dict) else []
    results = []
    for c in candidates[:20]:
        results.append(download_and_validate(c))
    summary['results']=results
    print(json.dumps(summary, indent=2))

if __name__=='__main__':
    main()
