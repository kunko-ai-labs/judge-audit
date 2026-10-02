"""INTERIM look at the completed v0.5 study runs (not the published analysis: 2,000 resamples,
no Holm until every confirmatory test exists). Reads committed/complete checkpoints only."""
import json, os, sys
W = os.environ["W"]
sys.path.insert(0, W + "/src")
from judge_audit.metrics.selective import (failure_auroc, failure_auroc_ci, paired_difference_test,
                                           coverage_at_risk_crossfit)

LABELS = {"banking77": "examples/banking77/labels-test.jsonl",
          "clinc150": "examples/clinc150/labels-test-banking-credit.jsonl"}
NB = 2000


def norm(t): return " ".join(t.lower().split())


def load(ds, slug):
    p = f"{W}/docs/runs/v05/{ds}/{slug}.ckpt.jsonl"
    if not os.path.exists(p):
        return None
    with open(p) as f:
        rows = [json.loads(l) for l in f if l.strip()]
    rec = {r["idx"]: r["judgments"][0] for r in rows if r["idx"] >= 0}
    with open(f"{W}/{LABELS[ds]}") as f:
        lab = [json.loads(l) for l in f if l.strip()]
    lab = [r for r in lab if "state" in r]
    if len(rec) < len(lab):
        return None
    out = []
    for i, r in enumerate(lab):
        j = rec[i]
        dec = (j.get("decision") or "").strip()
        if os.environ.get("LENIENT") and ":" in dec:   # "<option>: <its description>" -> option
            head = dec.split(":", 1)[0].strip()
            if head in r["questions"][0]["options"]:
                dec = head
        ok = dec.lower() == r["labels"]["intent"].lower()
        c = j.get("confidence") if j.get("parse_status", "parsed") == "parsed" else None
        out.append((c, ok, norm(r["state"])))
    return out


def auroc_of(pairs):
    cs = [(c, ok) for c, ok in pairs if c is not None]
    return failure_auroc([c for c, _ in cs], [ok for _, ok in cs])


RUNS = {"banking77": ["jev", "laya", "llm-gemini-3.6-flash", "llm-gemini-3.6-flash-sc5",
                      "llm-qwen3-8b", "llm-qwen3-8b-sc10"],
        "clinc150": ["jev", "laya", "llm-gemini-3.6-flash", "llm-gemini-3.6-flash-sc5",
                     "llm-qwen3-8b"]}
data = {}
for ds, slugs in RUNS.items():
    print(f"\n== {ds}")
    for s in slugs:
        d = load(ds, s)
        if d is None:
            print(f"{s:28s} not complete"); continue
        data[(ds, s)] = d
        n = len(d); acc = sum(ok for _, ok, _ in d) / n
        sc = [(c, ok, g) for c, ok, g in d if c is not None]
        a = failure_auroc([c for c, _, _ in sc], [ok for _, ok, _ in sc])
        ci = failure_auroc_ci([c for c, _, _ in sc], [ok for _, ok, _ in sc], n_boot=NB, seed=2026,
                              groups=[g for _, _, g in sc]).ci
        cov = {}
        for r in (0.05, 0.10):
            res = coverage_at_risk_crossfit([c for c, _, _ in sc], [ok for _, ok, _ in sc], r,
                                            groups=[g for _, _, g in sc], seed=2026, start_errors=2)
            cov[r] = (res.get("pooled") or {}).get("coverage")
        print(f"{s:28s} acc {acc:.3f}  AUROC {a:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]  "
              f"no-conf {n - len(sc)}  cert5% {cov[0.05]}  cert10% {cov[0.10]}")


def test(ds, a, b, label):
    A, B = data.get((ds, a)), data.get((ds, b))
    if A is None or B is None:
        print(f"{label}: not available yet"); return
    pa = [(c, ok) for c, ok, _ in A]; pb = [(c, ok) for c, ok, _ in B]
    t = paired_difference_test(pa, pb, auroc_of, n_boot=NB, seed=2026, groups=[g for *_, g in A])
    print(f"{label}: {a} − {b} = {t.difference:+.3f} [{t.ci[0]:+.3f}, {t.ci[1]:+.3f}] p={t.p_value:.4f}")


print("\n== confirmatory tests available now (raw p, no Holm yet)")
test("banking77", "llm-qwen3-8b-sc10", "llm-qwen3-8b", "T3")
test("banking77", "llm-gemini-3.6-flash-sc5", "llm-gemini-3.6-flash", "T5")
test("clinc150", "llm-gemini-3.6-flash-sc5", "llm-gemini-3.6-flash", "T6")
best = max(["llm-gemini-3.6-flash", "llm-gemini-3.6-flash-sc5"],
           key=lambda s: auroc_of([(c, ok) for c, ok, _ in data[("banking77", s)]]))
print(f"Gemini's best method on BANKING77 (by AUROC): {best}")
test("clinc150", "jev", best, "T8")
