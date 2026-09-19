# judge-audit — vision: the Moody's of AI judges

## The thesis in one sentence

Every vendor publishes its own benchmarks. No regulated company can deploy a
judge on the vendor's word. Someone has to be the independent authority that
rates judges. That someone is Kunko AI Labs.

## Why now

- TypeSafe comes out of stealth (2026-09-15, $40M) with "calibrated confidence"
  via RLCD as its central claim. A statistical, testable claim, with no
  independent verification.
- nikhilmudholkar's manual benchmark (1,565 emails, 111k views) shows the
  community *wants* independent audits. He did it by hand, once.
- LangChain already integrates Jev (`langchain-typesafe`, AutoModeMiddleware):
  the consumer ecosystem is growing; the verifier ecosystem is empty.

## The four layers (from open source to company)

### 1. Open-source harness (this, now)
`judge-audit run` — shadow mode against human-labeled decisions.
Metrics: ECE, reliability bins, accuracy-coverage curve, zero-error coverage,
real cost, p99. Anti-drift CI gate. Swappable judge (Jev today, anything tomorrow).

### 2. Judge Arena — the honesty leaderboard (distribution)
A public, continuously updated ranking of judges by **calibration**, not accuracy.
Leaderboards are distribution machines (Chatbot Arena proved it).
Each participant contributes its dataset (opt-in, anonymised) → the aggregated
dataset becomes the moat. House thesis: the moat is distribution + data gravity.

### 3. Evidence dossier for the AI Act (revenue)
European companies deploying judges need evidence for:
Art. 12 (logging), Art. 14 (human oversight), Art. 15 (accuracy/robustness).
We sell the automatically generated *evidence dossier*, not a certification.
Mandatory positioning: `adapted`, never "certified/compliant".

### 4. Continuous monitor (recurring)
"Datadog for judges": calibration monitoring in production, alert when drift
crosses the threshold, with the human-escalation threshold as the product.

## The Spain / EU wedge

The first "AI Act-ready" judge audit in Spanish. Regulated sectors (banking,
insurance, legal — banca, seguros, legal) *have* to demonstrate human oversight:
we do not sell them the judge, we sell them the proof that their judge can be
trusted. Own judges specialised in Spanish as phase 2 (backlog idea 29).

## Synergy with Agent Assurance

- Agent Assurance = the deterministic layer (declared vs observed, blocks).
- judge-audit = the probabilistic layer (is the judge honest?, audits).
- Together: the complete European "agent assurance" stack. Deterministic where
  it can be proven, probabilistic where it has to be measured.
