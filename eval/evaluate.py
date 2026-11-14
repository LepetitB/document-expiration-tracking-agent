"""Field-level accuracy of the extraction pipeline against data/samples/ground_truth.json.

    python -m eval.evaluate --engine rules            # offline baseline (.txt files)
    python -m eval.evaluate --engine claude --ext png # Claude Vision on images (needs API key, costs money)

Writes eval/results_<engine>_<ext>.md
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from app.extraction.extractor import extract

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples"


def _norm(s: str | None) -> str:
    return re.sub(r"[\s\-./]", "", (s or "")).lower()


def main() -> None:
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="rules", choices=["rules", "claude"])
    ap.add_argument("--ext", default="txt", choices=["txt", "png", "pdf"])
    args = ap.parse_args()

    truth = json.loads((SAMPLES / "ground_truth.json").read_text(encoding="utf-8"))
    rows, score = [], {"doc_type": 0, "expiry_date": 0, "doc_number": 0, "plate": 0}
    false_confident = sent_to_review = 0
    for name, t in truth.items():
        path = SAMPLES / f"{name}.{args.ext}"
        if not path.exists():
            continue
        ex = extract(path, args.engine)
        plate = ex.get("vehicle_plate") or ""
        ok = {
            "doc_type": ex.get("doc_type") == t["doc_type"],
            "expiry_date": str(ex.get("expiry_date")) == t["expiry_date"],
            "doc_number": _norm(t["doc_number"]) in _norm(ex.get("doc_number")),
            "plate": _norm(t["plate"]) in _norm(plate),
        }
        for k, v in ok.items():
            score[k] += v
        all_ok = all(ok.values())
        sent_to_review += ex["needs_review"]
        false_confident += (not all_ok) and (not ex["needs_review"])
        rows.append((name, ok, ex))

    n = len(rows) or 1
    lines = [f"# Evaluation — engine `{args.engine}`, files `*.{args.ext}`", "",
             f"Documents: **{len(rows)}**", "", "| Field | Accuracy |", "|---|---|"]
    lines += [f"| {k} | {v}/{len(rows)} ({v / n:.0%}) |" for k, v in score.items()]
    lines += ["", f"- Sent to human review: {sent_to_review}/{len(rows)}",
              f"- **False-confident** (wrong but auto-confirmed): {false_confident}/{len(rows)}", "",
              "| File | type | expiry | number | plate | extracted expiry | confidence |", "|---|---|---|---|---|---|---|"]
    mark = lambda b: "✅" if b else "❌"
    for name, ok, ex in rows:
        lines.append(f"| {name} | {mark(ok['doc_type'])} | {mark(ok['expiry_date'])} | {mark(ok['doc_number'])} | "
                     f"{mark(ok['plate'])} | {ex.get('expiry_date_raw')} → {ex.get('expiry_date')} | {ex['confidence']:.2f} |")
    report = "\n".join(lines)
    out = ROOT / "eval" / f"results_{args.engine}_{args.ext}.md"
    out.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\nsaved → {out}")


if __name__ == "__main__":
    main()
