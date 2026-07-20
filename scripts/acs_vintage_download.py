# -*- coding: utf-8 -*-
"""Download files with provenance sidecars into data/raw/acs/."""
import hashlib, os, sys, time, urllib.request

OUT = r"C:\Users\aersl\oc-transit-forecast\data\raw\acs"
os.makedirs(OUT, exist_ok=True)

def dl(url, fname=None):
    fname = fname or url.rsplit("/", 1)[-1]
    path = os.path.join(OUT, fname)
    if os.path.exists(path) and os.path.exists(path + ".provenance.txt"):
        print(f"SKIP (exists): {fname}")
        return path
    for k in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
                h = hashlib.sha256()
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
            size = os.path.getsize(path)
            with open(path + ".provenance.txt", "w", encoding="utf-8") as f:
                f.write(f"filename: {fname}\nsource_url: {url}\nbytes: {size}\n"
                        f"sha256: {h.hexdigest()}\n"
                        f"fetched: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
            print(f"OK {fname} {size} {h.hexdigest()}")
            return path
        except Exception as e:
            print(f"retry {k}: {fname}: {e}")
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"FAILED: {url}")

for url in sys.argv[1:]:
    dl(url)
