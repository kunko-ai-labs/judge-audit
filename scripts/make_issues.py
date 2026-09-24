"""Create labels + roadmap issues (5 epics, 11 stories) for kunko-ai-labs/judge-audit."""
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

API = "https://api.github.com"
REPO = "kunko-ai-labs/judge-audit"

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
        headers={"Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    add_surrogate_to_request(req, "custom.github", allowed_hosts=["api.github.com"])
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, read_json_response(resp) if resp.status != 204 else None
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, path, e.read()[:200])
        raise

# ---------- labels ----------
LABELS = [
    ("type:story", "0e8a16", "A scoped user story"),
    ("type:bug", "d73a4a", "Something is wrong"),
    ("priority:critical", "b60205", ""),
    ("priority:high", "d93f0b", ""),
    ("priority:medium", "fbca04", ""),
    ("priority:low", "0e8a16", ""),
    ("status:todo", "ededed", "Not started"),
    ("epic", "5319e7", "A capability spanning several stories"),
    ("area:judge", "1d76db", "Judge adapters"),
    ("area:runner", "1d76db", "Shadow-mode runner"),
    ("area:metrics", "1d76db", "Calibration metrics"),
    ("area:report", "1d76db", "Reports and charts"),
    ("area:integration", "1d76db", "External integrations"),
    ("area:docs", "1d76db", "Documentation"),
    ("area:ci", "1d76db", "CI gates"),
    ("good-first-issue", "7057ff", "Good for newcomers"),
]
for name, color, desc in LABELS:
    try:
        call("POST", f"/repos/{REPO}/labels",
             {"name": name, "color": color, "description": desc})
        print("label ok:", name)
    except Exception:
        print("label exists:", name)

# ---------- issues ----------
def story(sid, epic, title, priority, area, persona, estimate, milestone,
          as_a, want, so_that, criteria, notes="", deps="None", extra_labels=()):
    body = f"""## Story ID: {sid}

| Field | Value |
|-------|-------|
| **Epic** | {epic} |
| **Priority** | {priority} |
| **Area** | {area} |
| **Persona** | {persona} |
| **Estimate** | {estimate} |
| **Milestone** | {milestone} |

---

## 📖 User Story

**As a** {as_a},
**I want** {want},
**so that** {so_that}.

---

## ✅ Acceptance Criteria

{criteria}

---

## 📋 Technical Notes

{notes}

---

## 🔗 Dependencies

- Depends on: {deps}

---

## 🔐 Security & house rules

- [ ] Metrics are deterministic — no LLM in the measurement
- [ ] A judge adapter never fabricates confidence; unknown confidence is reported, not invented
- [ ] API keys never logged, never committed; network only inside judge adapters
- [ ] Sample datasets contain no real personal data; simulated judges are labeled SIMULATED

---

## 🏁 Definition of Done

- [ ] Code + tests merged into `main` via PR titled `type(scope): [{sid}] …`
- [ ] Fixture in `examples/` if a dataset, judge or report format was added
- [ ] `pytest -q` green on 3.10–3.12
- [ ] Epic table updated (`status:done`)
"""
    return (f"[{sid}] {title}",
            ["type:story", f"priority:{priority}", "status:todo", f"area:{area}"] + list(extra_labels),
            body)

def epic(eid, title, bet, persona, milestone, metric, guardrail, out_of_scope,
         description, goals, stories):
    rows = "\n".join(f"| {s} | {t} | `status:todo` |" for s, t in stories)
    body = f"""# 🎯 EPIC: {title}

## 🧭 Product block

| Field | Value |
|-------|-------|
| **Bet** | {bet} |
| **Persona** | {persona} |
| **Milestone** | {milestone} |
| **Primary success metric** | {metric} |
| **Guardrail metric** | {guardrail} |
| **Explicit out-of-scope** | {out_of_scope} |

---

## 📝 Description

{description}

## 🎯 Goals

{goals}

## 📖 User Stories

| ID | Title | Status |
|----|-------|--------|
{rows}

## ✅ Epic acceptance

- [ ] All stories closed and released
- [ ] Success metric measured and recorded in the milestone notes
- [ ] Guardrail metric intact
- [ ] Docs updated (`README.md` only for first-time readers; detail in `docs/`)

## 🔐 House rules check

- [ ] Metrics stay deterministic — no LLM in the measurement
- [ ] No fabricated confidence anywhere in the pipeline
- [ ] API keys never logged or committed
"""
    return (f"[{eid}] {title}", ["epic", "status:todo"], body)

ISSUES = [
epic("EP-001", "Viral demo: auditable sample report with charts",
     bet="now", persona="Developer", milestone="v0.1.0",
     metric="A first-time reader understands what an audit proves in 60 seconds; report screenshots are X/Dev.to-ready",
     guardrail="Every number labeled SIMULATED where simulated; metrics stay deterministic",
     out_of_scope="Real Jev API results (EP-002); hosted leaderboard (EP-004)",
     description=("Nobody adopts a measurement tool they can't picture. Before asking for API keys or datasets, "
                  "we show the artifact: a full audit report — ECE, reliability diagram, accuracy-coverage curve, "
                  "zero-error coverage, cost, p99 — from a synthetic email-routing dataset scored by a simulated "
                  "calibrated judge. The report is the product demo and the launch content."),
     goals="- [ ] 200-row synthetic dataset (DE/EN, 10 categories) under `examples/`\n- [ ] Seeded simulated judge, labeled SIMULATED everywhere\n- [ ] PNG charts + static HTML report with embedded charts\n- [ ] `docs/sample-report.md` wired for screenshots",
     stories=[("US-001-001", "Synthetic email-routing dataset"), ("US-001-002", "Simulated calibrated judge"),
              ("US-001-003", "Chart generation (PNG)"), ("US-001-004", "Static HTML audit report"),
              ("US-001-005", "Sample report doc for screenshots")]),

story("US-001-001", "EP-001 — Viral demo", "Synthetic email-routing dataset (200 DE/EN rows, 10 categories)",
      "high", "runner", "Developer", "1 day", "v0.1.0",
      as_a="a developer evaluating judge-audit", want="a realistic labeled dataset I can audit in one command",
      so_that="I see a full audit report without needing an API key or my own data.",
      criteria=("- [ ] **Given** a fresh checkout **when** I run `judge-audit run examples/email-routing/labels.jsonl --judge simulated` **then** 200 rows are scored with zero setup\n- [ ] **Given** the dataset **when** I inspect it **then** it covers 10 business-email categories in German and English with unambiguous labels\n- [ ] **Given** the dataset **when** I grep for personal data **then** there is none — every row is synthetic"),
      notes="- Entry point: `examples/email-routing/labels.jsonl`\n- Generator script (seeded) under `examples/email-routing/generate.py` so the dataset is reproducible"),

story("US-001-002", "EP-001 — Viral demo", "Simulated calibrated judge (seeded, labeled SIMULATED)",
      "high", "judge", "Developer", "1 day", "v0.1.0",
      as_a="a developer without a Jev API key", want="a judge adapter that behaves like a calibrated judge",
      so_that="I can run the full audit pipeline end to end today.",
      criteria=("- [ ] **Given** `--judge simulated` **when** the audit runs **then** confidence correlates with correctness (ECE < 0.08 on the synthetic set)\n- [ ] **Given** any output of the simulated judge **when** I read it **then** it is labeled SIMULATED and can never be mistaken for a real vendor audit"),
      notes="- Entry point: `src/judge_audit/judges/simulated.py`\n- Similar code: `src/judge_audit/judges/jev.py` (same `Judge` interface)\n- Depends on: US-001-001", deps="US-001-001"),

story("US-001-003", "EP-001 — Viral demo", "Chart generation: reliability diagram + accuracy-coverage PNG",
      "high", "report", "Developer", "2 days", "v0.1.0",
      as_a="a developer sharing an audit", want="PNG charts of calibration",
      so_that="I can paste the reliability diagram and the accuracy-coverage curve into X/Dev.to.",
      criteria=("- [ ] **Given** an `AuditResult` **when** I run the chart command **then** I get a reliability diagram (bins + diagonal) and an accuracy-coverage curve as PNG\n- [ ] **Given** the PNGs **when** viewed at 1200px wide **then** all labels are legible (X-ready)\n- [ ] **Given** stdlib-only core **when** charts are needed **then** matplotlib is an optional extra, never a hard dependency"),
      notes="- Entry point: `src/judge_audit/charts.py` (new module)\n- Data already available: `AuditResult.reliability`, `AuditResult.curve`"),

story("US-001-004", "EP-001 — Viral demo", "Static HTML audit report with embedded charts",
      "medium", "report", "Reviewer", "2 days", "v0.1.0",
      as_a="a reviewer receiving an audit", want="a single HTML file with the report and charts embedded",
      so_that="I can open it in a browser and forward it — no app, no backend. (This is our 'front' for now.)",
      criteria=("- [ ] **Given** `judge-audit run … --format html` **when** it finishes **then** one self-contained HTML file exists with metrics, tables and base64-embedded charts\n- [ ] **Given** the HTML file **when** opened with no network **then** everything renders"),
      notes="- Entry point: `src/judge_audit/report.py` (extend `render_markdown` with `render_html`)\n- Depends on: US-001-003", deps="US-001-003"),

story("US-001-005", "EP-001 — Viral demo", "Sample report doc ready for screenshots (launch asset)",
      "medium", "docs", "Developer", "1 day", "v0.1.0",
      as_a="Vane launching judge-audit", want="`docs/sample-report.md` with the rendered report and charts",
      so_that="the launch thread and Dev.to post have real artifacts to show, honestly labeled as simulated.",
      criteria=("- [ ] **Given** `docs/sample-report.md` **when** rendered on GitHub **then** it shows the full report: headline metrics, both charts, and the SIMULATED banner\n- [ ] **Given** the launch post **when** I screenshot the report **then** nothing in the shot can be misread as a real Jev audit"),
      notes="- Depends on: US-001-001, US-001-002, US-001-003", deps="US-001-001, US-001-002, US-001-003",
      extra_labels=("good-first-issue",)),

epic("EP-002", "First real audit: Jev on the live API",
     bet="now", persona="Developer", milestone="v0.2.0",
     metric="One published independent audit of Jev with measured ECE, cost and p99 — the launch content",
     guardrail="No vendor claim repeated without measurement; waitlist key stored only in env",
     out_of_scope="Beating vendor benchmarks; hosting the arena",
     description=("The scaffold's `JevJudge` is written against the documented API but has never touched it. "
                  "This epic unblocks on TypeSafe waitlist access (or AI Gateway access) and produces the first "
                  "real artifact: an independent Jev audit. Until then it stays open and blocked."),
     goals="- [ ] `JevJudge` validated against the live `POST /v1/systemone` endpoint\n- [ ] First independent audit published (the nikhilmudholkar-style post, but automated)",
     stories=[("US-002-001", "Validate JevJudge against live TypeSafe API"),
              ("US-002-002", "Publish first independent Jev audit")]),

story("US-002-001", "EP-002 — First real audit", "Validate JevJudge against live TypeSafe API",
      "high", "judge", "Developer", "2 days", "v0.2.0",
      as_a="a developer with a TypeSafe API key", want="`JevJudge` to score the synthetic dataset against the live API",
      so_that="the adapter is proven against reality, not just docs.",
      criteria=("- [ ] **Given** `TYPESAFE_API_KEY` in env **when** I run the audit on the synthetic dataset **then** every question returns a decision + confidence with no parse errors\n- [ ] **Given** the live run **when** I compare measured latency/cost **then** they are recorded per judgment (no hardcoded prices except the published input rate)"),
      notes="- Entry point: `src/judge_audit/judges/jev.py`\n- Blocked on: TypeSafe waitlist or AI Gateway access"),

story("US-002-002", "EP-002 — First real audit", "Publish first independent Jev audit",
      "high", "docs", "Developer", "2 days", "v0.2.0",
      as_a="Vane launching judge-audit", want="a public audit post with measured numbers",
      so_that="the project launches with proof, not promises.",
      criteria=("- [ ] **Given** the live audit **when** published **then** it reports ECE, accuracy-coverage, cost/1k and p99 measured by us — with the dataset and command to reproduce\n- [ ] **Given** the post **when** read **then** vendor claims are cited as vendor claims, ours as measured"),
      notes="- Depends on: US-002-001", deps="US-002-001"),

epic("EP-003", "AI Act evidence pack",
     bet="next", persona="Auditor", milestone="v0.3.0",
     metric="One command produces the evidence bundle an auditor asks for: receipts + calibration report + declared metrics",
     guardrail="`adapted` positioning — never 'certified' or 'compliant'",
     out_of_scope="Legal advice; hosting customer data",
     description=("EU deployers of AI judges will need evidence for AI Act Art. 12 (logging), Art. 14 (human oversight) "
                  "and Art. 15 (declared accuracy). This epic turns the audit into a shippable evidence pack. "
                  "See `docs/landscape-brief.md` §3."),
     goals="- [ ] Per-decision receipt (Art. 12)\n- [ ] MCE metric (worst-case, what regulators ask)\n- [ ] Evidence dossier export",
     stories=[("US-003-001", "Decision receipt per judgment (Art. 12 logging)"),
              ("US-003-002", "MCE metric (worst-case calibration)"),
              ("US-003-003", "Evidence dossier export")]),

story("US-003-001", "EP-003 — AI Act evidence", "Decision receipt per judgment (Art. 12 logging)",
      "high", "runner", "Auditor", "2 days", "v0.3.0",
      as_a="an auditor", want="every judgment to emit a signed receipt",
      so_that="the deployer has Art. 12 logging material: input hash, decision, confidence, threshold, timestamp, model version, escalation.",
      criteria=("- [ ] **Given** an audit run with `--receipts` **when** it finishes **then** one JSONL receipt per judgment exists with: sha256(state), decision, confidence, threshold applied, timestamp, judge name+version, escalated_to_human bool\n- [ ] **Given** a receipt **when** inspected **then** it contains no raw personal data — only the hash"),
      notes="- Entry point: `src/judge_audit/runner.py`\n- See docs/landscape-brief.md §3 (Art. 12)"),

story("US-003-002", "EP-003 — AI Act evidence", "MCE metric (worst-case calibration for regulators)",
      "medium", "metrics", "Auditor", "1 day", "v0.3.0",
      as_a="an auditor", want="Maximum Calibration Error next to ECE",
      so_that="I can answer the regulator's question: not the average case, the worst bin.",
      criteria=("- [ ] **Given** confidences+labels **when** I call the new function **then** MCE = max over bins |accuracy − confidence| is returned\n- [ ] **Given** the report **when** rendered **then** MCE appears next to ECE"),
      notes="- Entry point: `src/judge_audit/metrics/calibration.py` (next to `expected_calibration_error`)\n- Pure function, fully unit-testable",
      extra_labels=("good-first-issue",)),

story("US-003-003", "EP-003 — AI Act evidence", "Evidence dossier export (MD bundle)",
      "medium", "report", "Auditor", "3 days", "v0.3.0",
      as_a="a CISO", want="`judge-audit dossier` to bundle receipts + calibration report + declared metrics",
      so_that="I can hand one folder to an auditor for the conformity assessment.",
      criteria=("- [ ] **Given** a completed audit **when** I run the dossier command **then** a folder contains: receipts JSONL, calibration report (MD+HTML), declared-metrics sheet, and a README mapping each file to its AI Act article\n- [ ] **Given** the dossier README **when** read **then** it says 'adapted, not certified' — no compliance claim"),
      notes="- Entry point: new `dossier` subcommand in `src/judge_audit/cli.py`\n- Depends on: US-003-001", deps="US-003-001"),

epic("EP-004", "Judge Arena MVP: honesty leaderboard",
     bet="later", persona="Developer", milestone="v0.4.0",
     metric="First public ranking of ≥3 judges by calibration on one shared dataset",
     guardrail="Submissions are reproducible (dataset + command published); no pay-to-rank",
     out_of_scope="Hosted execution of judges; private datasets",
     description=("A public, continuously updated leaderboard ranking judges by calibration — the 'honesty leaderboard'. "
                  "Leaderboards are distribution machines; every participant contributes (opt-in, anonymized) to the "
                  "shared benchmark, which becomes the data moat. Nobody has built this: JudgeBench ranks accuracy, "
                  "not calibration."),
     goals="- [ ] Submission spec (dataset + audit-result.json + reproduce command)\n- [ ] Static leaderboard page generated from submissions",
     stories=[("US-004-001", "Leaderboard submission spec + static page")]),

story("US-004-001", "EP-004 — Judge Arena MVP", "Leaderboard submission spec + static page",
      "medium", "integration", "Developer", "3 days", "v0.4.0",
      as_a="a judge author", want="a spec to submit my judge's audit",
      so_that="it appears on the honesty leaderboard next to the others.",
      criteria=("- [ ] **Given** the spec **when** I follow it **then** my submission is: dataset (or hash of the shared one), `audit-result.json`, and the exact reproduce command\n- [ ] **Given** ≥1 submissions **when** the page builds **then** a static page ranks judges by ECE with links to each audit"),
      notes="- Static site generation keeps it free to host; no backend in v0.4.0"),

epic("EP-005", "LLM-as-judge adapter (runnable without a Jev key)",
     bet="next", persona="Developer", milestone="v0.2.0",
     metric="Anyone with an OpenAI/Anthropic key can run a full audit today — zero TypeSafe dependency",
     guardrail="Confidence extraction is documented as heuristic; never presented as calibrated",
     out_of_scope="Fine-tuning judges; supporting every provider",
     description=("Jev access is waitlisted. An LLM-as-judge adapter lets anyone run judge-audit today with a key they "
                  "already have — it also makes the tool judge-agnostic in practice, which is the whole point."),
     goals="- [ ] One provider-agnostic LLM judge (OpenAI-compatible endpoint)\n- [ ] Documented confidence heuristic with honesty caveats",
     stories=[("US-005-001", "Generic LLM judge adapter with confidence extraction")]),

story("US-005-001", "EP-005 — LLM-as-judge adapter", "Generic LLM judge adapter with confidence extraction",
      "high", "judge", "Developer", "3 days", "v0.2.0",
      as_a="a developer without a Jev key", want="`--judge llm` against any OpenAI-compatible endpoint",
      so_that="I can audit an LLM judge's calibration today.",
      criteria=("- [ ] **Given** `OPENAI_BASE_URL` + key **when** I run the audit **then** decisions and heuristic confidences are recorded per judgment\n- [ ] **Given** the report **when** rendered **then** confidences are labeled HEURISTIC — the tool never claims an LLM's verbalized confidence is calibrated"),
      notes="- Entry point: `src/judge_audit/judges/llm.py` (new)\n- House rule applies doubly here: heuristic confidence must never look measured"),
]

created = []
for title, labels, body in ISSUES:
    st, data = call("POST", f"/repos/{REPO}/issues",
                    {"title": title, "body": body, "labels": labels})
    created.append((data["number"], title))
    print("issue ok:", data["number"], title[:60])
print("TOTAL:", len(created))
