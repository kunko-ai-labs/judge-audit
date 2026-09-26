# Three ways to read a chat model's confidence

**Short version.** v0.4 measured every chat model by the number it writes ("confidence: 0.9") and Jev by the probability its model assigns to the chosen option. Part of Jev's lead may therefore be the *method*, not the *model*. v0.5 reads each chat model's confidence more than one way, on the same rows, and compares the methods **within the same model**: open-weight models run locally are read all three ways; hosted models (Claude, Gemini, GPT-5) two ways, verbalized and self-consistency, because no judge here reads a hosted model's token probabilities yet. That comparison does not depend on any vendor, the literature has not settled it, and it answers the question this repository asks: can a judge's declared confidence decide what to automate?

## The three methods

| Method | What is measured | Judge in this repository | Available for |
|---|---|---|---|
| **Verbalized** | The number the model writes next to its answer, asked for in the prompt | `llm` (default) | every chat model |
| **Token log-probability** | The probability the model itself assigns to answering exactly each option: its tokens, then the end of its turn, normalised over the options | `logprob` (local, MLX) | open-weight models run locally. Hosted endpoints that return log-probabilities can be found with `scripts/logprob_smoke.py`, but no judge reads them yet |
| **Self-consistency** | Ask the same question k times at a sampling temperature; the decision is the majority, the confidence is the share of samples that gave it | `llm` with `LLM_SAMPLES=k`, `LLM_TEMPERATURE` | every chat model (k times the cost) |

Each method is its own row in every table (for self-consistency the judge is named `llm:<model>:sc<k>`); the three are **never averaged**. A model whose API returns no log-probabilities says so; the method is not imputed.

## Why within the same model

Comparing Jev's probability with Gemini's verbalized number mixes two things: the model and the way its confidence is read. Holding the model fixed and changing only the read-out isolates the second one. If Gemini's self-consistency ranks its errors as well as Jev's probability does, v0.4's gap was mostly method; if not, it was mostly model. Either answer is useful to someone choosing a judge.

## What the literature says, and why the question is open

- **Verbalized is not simply "worst".** For RLHF-tuned chat models, verbalized confidence was often *better* calibrated than conditional token probabilities on TriviaQA, SciQ and TruthfulQA (Tian et al., EMNLP 2023).
- **Verbalized is overconfident and coarse.** Values cluster between 80 % and 100 %, often in multiples of 5; sampling several answers and measuring their consistency helps (Xiong et al., ICLR 2024).
- **Token probabilities depend on choices rarely written down**: which answer string is scored, how its tokens are combined, under which context (Kim & Kang 2026). This repository writes them down (below) and the pre-registration fixes them.
- **Self-consistency** as a decision rule, majority over sampled answers, comes from Wang et al. (ICLR 2023); using the agreement as a confidence is one of the consistency-based methods Xiong et al. evaluate.

## Choices this repository makes, and their caveats

**Token log-probability (`logprob`)**
- The prompt is tokenised and run once, exactly as generation sees it; each option's tokens extend that cached prompt. An option scores the sum of its tokens' log-probabilities plus the log-probability of ending the turn right there, so `top_up` is not credited with the mass of `top_up_failed`.
- Log-probabilities are computed in float32. In bfloat16 (the 4-bit community checkpoints) a large-vocabulary softmax turned 0.95 into 1.0; a test compares a bfloat16 model with a float64 reference.
- The confidence is P(option | the answer is one of the options). The share of probability that fell on the options before normalising (`option_mass`) is kept and must be printed next to any ECE: a small one means the normalisation, not the model, made the answer confident. Normalising is a choice; the pre-registration fixes it.
- **It is not the verbalized judge with another read-out.** Its prompt, its decision rule (the most probable listed option, not a parsed free answer) and its confidence all differ. A difference between the two rows is not attributable to the confidence method alone.
- Thinking is switched off, so the probability read is that of a direct answer.

**Self-consistency (`LLM_SAMPLES`, `LLM_TEMPERATURE`)**
- Ties go to the decision drawn first (random with respect to the option order). A sample with no answer counts in k and votes for nothing.
- **Without reasoning it approximates the token probability.** The prompt asks for JSON only; for a model that does not reason before answering, the vote share at temperature 1 is a noisy k-sample estimate of the probability of its answer. That makes it the way to estimate that probability where an API returns none (most hosted frontier models), and it differs from it for models that reason. How close the two are is measured where both exist.
- **Coarse.** At k = 5 it takes at most five values; ties are the rule. The metrics never break ties in the judge's favour (see [automation at risk](automation-at-risk.md)). A unanimous wrong answer has confidence 1.0, which makes NLL infinite; reports print ∞ with the count.
- Several samples at temperature 0 are refused (they would measure the provider's nondeterminism). Models that refuse a temperature parameter use `LLM_TEMPERATURE=default`, recorded as "provider default".
- k times the calls, cost and latency. The verbalized number of every sample is kept, so verbalized confidence at that temperature comes from the same calls for free.

**Verbalized** is unchanged from v0.4 (temperature 0, one call).

## Which models expose log-probabilities

| Model family or path | Token log-probabilities | Basis |
|---|---|---|
| Claude (Messages API) | no | the official API reference lists no such parameter |
| OpenAI reasoning models (GPT-5 family) | no | OpenAI developer forum |
| Recent Gemini models | reported no | a Google developer-forum thread; checked per model with the smoke test |
| Open-weight models run locally (MLX, llama.cpp, Ollama ≥ 0.12.11) | yes | a forward pass returns the logits; Ollama's release notes |
| Open-weight models through a hosted OpenAI-compatible endpoint | depends on the endpoint | checked per model and endpoint with `scripts/logprob_smoke.py` before any run |

So: verbalized and self-consistency for every chat model; token log-probability for open-weight models run locally. Reading log-probabilities from a hosted endpoint that returns them would need a new judge path; it is not implemented.

Sources: [reading list](reading-list.md) § Confidence of language models.
