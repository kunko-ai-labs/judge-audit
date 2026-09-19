# Brief: the AI-judge audit landscape (2026-09-18)

Research to position judge-audit. Sources with URLs in each section.

## 1. The category is empty

Judges keep getting cheaper (Jev, Patronus's Glider, Galileo's Luna) and
platforms keep using them (Galileo, Patronus AI, Braintrust, Arize Phoenix,
DeepEval, Ragas). **None of them audits the judge's calibration as a product.**
All of them evaluate applications *using* judges; nobody publishes "is your
judge's confidence honest?".

Analogy: there are labs that sell thermometers, but no body that checks the
thermometers measure correctly.

- Galileo: metrics and guardrails on proprietary Luna models (black box —
  you cannot audit the auditor). Enterprise pricing.
- Patronus: Lynx and Glider are open source (auditable), but no calibration reports.
- Braintrust: aggregates scores, no calibration curves; short retention (30 days on Pro).
- DeepEval: open-source framework, ideal to *build* the calibration module on —
  not a competitor.

Sources: https://thenewstack.io/galileo-agent-control-open-source/ ·
https://siliconangle.com/2024/12/19/patronus-ai-releases-glider-small-high-performance-ai-evaluator-model-models/ ·
https://deepeval.com

## 2. Calibration standards

The "minimum credible package" of an audit report:
- **ECE** (Expected Calibration Error) — the de facto standard (Naeini et al. 2015,
  Guo et al. 2017). https://link.springer.com/article/10.1007/s10994-023-06336-7
- **Reliability diagrams** — accuracy vs confidence per bin; the diagonal is honesty.
- **Accuracy-coverage curves** (selective prediction) — what share can I automate at
  what error rate. This is what nikhilmudholkar's viral benchmark did.
  https://x.com/nikhilmudholkar/status/2100604560335139083

Differentiators: **MCE** (Maximum Calibration Error, worst case — what a regulator
asks for) and **conformal prediction** (coverage guarantees; a research line,
not something to claim yet).

## 3. What the AI Act requires (EU Regulation 2024/1689)

Applies to high-risk systems (Annex III: credit scoring, recruitment, insurance,
justice). An AI judge in those contexts falls inside.
Requirements enter into force on **2 Dec 2027** → a window of ~15 months to be the
de facto standard before it becomes mandatory.

- **Art. 12 (record-keeping):** automatic logs over the whole lifetime of the system.
  → Every judgment must emit a "receipt": input hash, decision, confidence,
  threshold applied, timestamp, model version, whether it escalated to a human.
- **Art. 14 (human oversight):** the overseer must understand the system's capabilities
  and *limitations* and be able to override decisions.
  → The calibration report is the evidence: "below 70 % confidence it fails half
  the time, which is why the escalation threshold is at X". Without numbers,
  human oversight is theatre.
- **Art. 15 (accuracy/robustness):** (3) accuracy metrics "shall be declared in the
  instructions for use"; (2) the Commission *shall encourage the development of
  benchmarks and measurement methodologies*.
  → Art. 15(2) is an explicit regulatory invitation to build this.

The minimum "evidence dossier": (i) per-decision receipts, (ii) a calibration
report that justifies the escalation threshold, (iii) declared metrics,
(iv) a production drift monitor, (v) technical documentation per Art. 11 / Annex IV.
*(Interpretation from the articles — legal validation pending.)*

Sources: https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14 ·
https://artificialintelligenceact.eu/article/15/

## 4. Existing leaderboards (none on calibration)

- JudgeBench (ICLR 2025): ranks judges by accuracy — not calibration.
  https://arxiv.org/abs/2410.12784v2
- "Judge's Verdict" (2025): 54 judges by correlation with humans — not calibration.
  https://arxiv.org/pdf/2510.09738
- JudgeBiasBench / MM-JudgeBench: measure biases — not calibration.
- LMSYS Chatbot Arena: human preference over models — not judges.

**No public leaderboard ranks judges by calibration.**
(Absence of evidence, not evidence of absence — re-verify before stating it
publicly.)

## 5. Risks

- If Galileo/Braintrust add "calibration reports", they compete from above.
  Defence: open source, portable (CI-first, no data lock-in) and European
  (EU residency, AI Act narrative).
- Still to verify: official Galileo/Confident AI pricing; conformal prediction
  as a standard; exact composition of the dossier (lawyer).
