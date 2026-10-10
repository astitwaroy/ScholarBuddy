"""
Command line:

    python -m app.cli migrate
    python -m app.cli ingest [--force] [--only DOC_ID ...]
    python -m app.cli eval [--k 6] [--answers] [--no-vectors]
    python -m app.cli ask "Which scholarships need 80th percentile?"
"""

from __future__ import annotations

import argparse
import json
import logging

from .db import migrate


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    ing = sub.add_parser("ingest")
    ing.add_argument("--force", action="store_true")
    ing.add_argument("--only", nargs="*")
    ev = sub.add_parser("eval")
    ev.add_argument("--k", type=int, default=6)
    ev.add_argument("--answers", action="store_true", help="also evaluate generated answers (uses the model)")
    ev.add_argument("--no-vectors", action="store_true", help="keyword search only")
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    a = p.parse_args()

    migrate()
    if a.cmd == "ingest":
        from .ingest.pipeline import ingest_all

        print(ingest_all(force=a.force, only=a.only).summary())
    elif a.cmd == "eval":
        from .evaluate import run_answer_eval, run_retrieval_eval

        r = run_retrieval_eval(k=a.k, use_vectors=not a.no_vectors)
        print(json.dumps({k: v for k, v in r.items() if k not in ("misses",)}, indent=2))
        for m in r["misses"]:
            print("MISS:", m)
        if a.answers:
            print(json.dumps(run_answer_eval(), indent=2))
    elif a.cmd == "ask":
        from .answer import answer

        print(json.dumps(answer(a.question), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
