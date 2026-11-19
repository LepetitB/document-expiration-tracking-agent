"""Accuracy, cost and latency of the extraction pipeline against data/samples/ground_truth.json.

    python -m eval.evaluate --engine rules                    # offline baseline (.txt files)
    python -m eval.evaluate --engine claude --ext png         # Claude Vision with CLAUDE_MODEL (costs money)
    python -m eval.evaluate --engine claude --ext png --model claude-haiku-5-5
    python -m eval.evaluate --compare                         # Opus / Sonnet / Haiku side by side (costs money)

Writes eval/results_<engine>[_<model>]_<ext>.md, raw numbers in eval/runs/*.json,
and for --compare eval/model_comparison.md.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import time
from datetime import datetime
from pathlib import Path

from app import config
from app.extraction.extractor import extract

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples"
RUNS = ROOT / "eval" / "runs"
DOCS_PER_YEAR = 130  # 40 vehicles x 3 documents + ~10 driver licences (see docs/01-rationale.md)
COMPARE_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]


def _norm(s: str | None) -> str:
    return re.sub(r"[\s\-./]", "", (s or "")).lower()


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, math.ceil(0.95 * len(s)) - 1)]


def evaluate(engine: str, ext: str, model: str | None = None) -> dict:
    truth = json.loads((SAMPLES / "ground_truth.json").read_text(encoding="utf-8"))
    rows, score = [], {"doc_type": 0, "expiry_date": 0, "doc_number": 0, "plate": 0}
    false_confident = sent_to_review = 0
    for name, t in truth.items():
        path = SAMPLES / f"{name}.{ext}"
        if not path.exists():
            continue
        t0 = time.perf_counter()
        try:
            ex = extract(path, engine, model)
        except Exception as e:  # count an API failure as a wrong, reviewed document
            ex = {"doc_type": None, "expiry_date": None, "needs_review": True, "confidence": 0.0,
                  "problems": [f"error: {e}"], "usage": None}
        seconds = time.perf_counter() - t0
        plate = ex.get("vehicle_plate") or ""
        ok = {
            "doc_type": ex.get("doc_type") == t["doc_type"],
            "expiry_date": str(ex.get("expiry_date")) == t["expiry_date"],
            "doc_number": _norm(t["doc_number"]) in _norm(ex.get("doc_number")),
            "plate": (_norm(t["plate"]) in _norm(plate)) if "plate" in t
                     else (_norm(t["holder"]) in _norm(ex.get("holder_name"))),
        }
        for k, v in ok.items():
            score[k] += v
        all_ok = all(ok.values())
        sent_to_review += bool(ex["needs_review"])
        false_confident += (not all_ok) and (not ex["needs_review"])
        usage = ex.get("usage") or {}
        rows.append({"file": name, "ok": ok, "all_ok": all_ok, "needs_review": bool(ex["needs_review"]),
                     "expiry_raw": ex.get("expiry_date_raw"), "expiry": str(ex.get("expiry_date")),
                     "confidence": ex.get("confidence", 0), "problems": ex.get("problems", []),
                     "seconds": round(usage.get("seconds", seconds), 2),
                     "input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0),
                     "cost_thb": usage.get("cost_thb") or 0.0, "served_by": usage.get("model")})

    n = len(rows) or 1
    secs = [r["seconds"] for r in rows]
    cost = [r["cost_thb"] for r in rows]
    summary = {
        "engine": engine, "model": model or (config.CLAUDE_MODEL if engine == "claude" else "-"), "ext": ext,
        "documents": len(rows), "field_accuracy": {k: v / n for k, v in score.items()},
        "all_fields_correct": sum(r["all_ok"] for r in rows), "sent_to_review": sent_to_review,
        "false_confident": false_confident,
        "seconds_avg": statistics.mean(secs) if secs else 0, "seconds_p95": _p95(secs),
        "input_tokens_avg": statistics.mean(r["input_tokens"] for r in rows) if rows else 0,
        "output_tokens_avg": statistics.mean(r["output_tokens"] for r in rows) if rows else 0,
        "thb_per_doc": statistics.mean(cost) if cost else 0, "thb_total": sum(cost),
        "thb_per_year": (statistics.mean(cost) if cost else 0) * DOCS_PER_YEAR,
        "usd_to_thb": config.USD_TO_THB, "measured_at": datetime.now().isoformat(timespec="seconds"),
    }
    return {"summary": summary, "rows": rows}


def write_report(result: dict) -> Path:
    s, rows = result["summary"], result["rows"]
    tag = f"{s['engine']}_{s['model'].replace('claude-', '')}" if s["engine"] == "claude" else s["engine"]
    lines = [f"# Evaluation — engine `{s['engine']}`, model `{s['model']}`, files `*.{s['ext']}`", "",
             f"Documents: **{s['documents']}** · measured {s['measured_at']}", "",
             "| Field | Accuracy |", "|---|---|"]
    lines += [f"| {k} | {v:.0%} |" for k, v in s["field_accuracy"].items()]
    lines += ["", f"- All fields correct: {s['all_fields_correct']}/{s['documents']}",
              f"- Sent to human review: {s['sent_to_review']}/{s['documents']}",
              f"- **False-confident** (wrong but auto-confirmed): {s['false_confident']}/{s['documents']}",
              f"- Latency: avg **{s['seconds_avg']:.1f} s**, p95 {s['seconds_p95']:.1f} s per document",
              f"- Tokens per document: ~{s['input_tokens_avg']:.0f} in / ~{s['output_tokens_avg']:.0f} out",
              f"- Cost: **{s['thb_per_doc']:.3f} THB per document** · {s['thb_total']:.2f} THB this run · "
              f"~{s['thb_per_year']:.0f} THB/year for {DOCS_PER_YEAR} documents (1 USD = {s['usd_to_thb']} THB)", "",
              "| File | type | expiry | number | plate/driver | extracted expiry | conf. | review | s | tokens in/out | THB |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    mark = lambda b: "✅" if b else "❌"  # noqa: E731
    for r in rows:
        ok = r["ok"]
        lines.append(f"| {r['file']} | {mark(ok['doc_type'])} | {mark(ok['expiry_date'])} | {mark(ok['doc_number'])} | "
                     f"{mark(ok['plate'])} | {r['expiry_raw']} → {r['expiry']} | {r['confidence']:.2f} | "
                     f"{'🟣' if r['needs_review'] else '-'} | {r['seconds']:.1f} | "
                     f"{r['input_tokens']}/{r['output_tokens']} | {r['cost_thb']:.3f} |")
    out = ROOT / "eval" / f"results_{tag}_{s['ext']}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{tag}_{s['ext']}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def write_comparison(results: list[dict]) -> Path:
    lines = ["# Model comparison — same documents, same prompt and pipeline", "",
             f"Measured {results[0]['summary']['measured_at']} · {results[0]['summary']['documents']} documents "
             f"(`*.{results[0]['summary']['ext']}`) · 1 USD = {config.USD_TO_THB} THB · "
             f"yearly cost assumes {DOCS_PER_YEAR} documents/year", "",
             "| Model | All fields correct | False-confident | Sent to review | Avg s/doc | p95 s | "
             "Tokens in/out per doc | THB/doc | THB/year |",
             "|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|"]
    for r in results:
        s = r["summary"]
        lines.append(f"| {s['model']} | {s['all_fields_correct']}/{s['documents']} | {s['false_confident']} | "
                     f"{s['sent_to_review']} | {s['seconds_avg']:.1f} | {s['seconds_p95']:.1f} | "
                     f"{s['input_tokens_avg']:.0f} / {s['output_tokens_avg']:.0f} | {s['thb_per_doc']:.3f} | "
                     f"{s['thb_per_year']:.0f} |")
    out = ROOT / "eval" / "model_comparison.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> None:
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="rules", choices=["rules", "claude"])
    ap.add_argument("--ext", default="txt", choices=["txt", "png", "pdf"])
    ap.add_argument("--model", default=None, help="Claude model id (default: CLAUDE_MODEL)")
    ap.add_argument("--compare", action="store_true", help="run Opus / Sonnet / Haiku on the PNG set")
    args = ap.parse_args()

    if args.compare:
        results = []
        for m in COMPARE_MODELS:
            print(f"… {m}", flush=True)
            res = evaluate("claude", "png", m)
            print(f"   report → {write_report(res)}", flush=True)
            results.append(res)
        out = write_comparison(results)
        print(out.read_text(encoding="utf-8"))
        return

    res = evaluate(args.engine, args.ext, args.model)
    out = write_report(res)
    print(out.read_text(encoding="utf-8"))
    print(f"saved → {out}")


if __name__ == "__main__":
    main()
