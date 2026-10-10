"""
Download the official source documents listed in data/catalog.json into data/raw/.

Some government sites refuse requests from cloud servers or from outside India. Run this once
on your own computer (no extra packages needed), commit data/raw/, and the server will index
those files instead of downloading them itself.

    python3 tools/download_sources.py
"""

import json
import pathlib
import ssl
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def get(url: str, verify: bool = True) -> bytes:
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,*/*"})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return r.read()


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    docs = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))["documents"]
    failed = 0
    for d in docs:
        out = RAW / f"{d['id']}.pdf"
        if out.exists() and out.stat().st_size > 1000:
            print(f"  have  {d['id']}")
            continue
        try:
            try:
                data = get(d["url"])
            except ssl.SSLError:
                data = get(d["url"], verify=False)  # some government sites send incomplete certificate chains
            if not (data[:5] == b"%PDF-" or b"<html" in data[:2000].lower()):
                raise ValueError("response is not a PDF")
            out.write_bytes(data)
            print(f"  saved {d['id']}  ({len(data) // 1024} KB)")
        except Exception as e:  # keep going; report at the end
            failed += 1
            print(f"  FAILED {d['id']}: {e}\n         {d['url']}")
    print(f"\n{len(docs) - failed} of {len(docs)} documents in {RAW}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
