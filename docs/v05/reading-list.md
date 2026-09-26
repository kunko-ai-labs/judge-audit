# Reading list: what v0.5 rests on

This is every source a v0.5 design choice depends on, and what we took from each. A claim in the study that cites none of these rests on the repository's own evidence (checkpoints under `docs/runs/`). Where a source was read only through a summary or a secondary report, it says so.

## Calibration and selective prediction

| Source | What we took from it |
|---|---|
| Guo, Pleiss, Sun & Weinberger, *On Calibration of Modern Neural Networks*, ICML 2017 | ECE with equal-width bins; temperature scaling, used post hoc for the fine-tuned classifier in v0.4 and labelled as such |
| Geifman & El-Yaniv, [*Selective Classification for Deep Neural Networks*](https://proceedings.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html), NeurIPS 2017 | Choosing a confidence threshold that guarantees a risk with high probability: the idea behind "coverage at error ≤ X %" |
| Geifman, Uziel & El-Yaniv, *Bias-Reduced Uncertainty Estimation for Deep Neural Classifiers*, ICLR 2019 | The area under the risk–coverage curve (AURC) as a ranking metric |
| Angelopoulos, Bates, Candès, Jordan & Lei, *Learn then Test: Calibrating Predictive Algorithms to Achieve Risk Control*, Annals of Applied Statistics 2025 | Fixed-sequence testing over thresholds, so trying many thresholds does not inflate the error guarantee |
| Jung, Brahman & Choi, [*Trust or Escalate: LLM Judges with Provable Guarantees for Human Agreement*](https://arxiv.org/abs/2407.18370), ICLR 2025 | The same guarantee applied to LLM judges: automate when confident, escalate otherwise |
| Clopper & Pearson, *The use of confidence or fiducial limits illustrated in the case of the binomial*, Biometrika 1934 | The exact one-sided bound behind "0 errors in 299 rows certifies below 1 %" |
| Wilson, *Probable inference, the law of succession, and statistical inference*, JASA 1927 | The interval on the share of likely label errors in the relabelled sample |

## Confidence of language models

| Source | What we took from it |
|---|---|
| Tian et al., [*Just Ask for Calibration*](https://aclanthology.org/2023.emnlp-main.330/), EMNLP 2023 | For RLHF-tuned chat models, verbalized confidence was often better calibrated than token probabilities. This is why "verbalized is worst" is not assumed |
| Xiong et al., [*Can LLMs Express Their Uncertainty?*](https://openreview.net/forum?id=gjeQKFxFpZ), ICLR 2024 | Verbalized confidence clusters at 80–100 % in multiples of 5; consistency among sampled answers helps. We could not read their exact aggregation formula (the paper was unreachable from the environment that wrote this), so v0.5 defines its own, the majority's share, and does not claim theirs |
| Wang et al., *Self-Consistency Improves Chain of Thought Reasoning in Language Models*, ICLR 2023 | The majority vote over sampled answers |
| Kim & Kang 2026, [arXiv:2605.27752](https://arxiv.org/abs/2605.27752) | Verbalized-vs-token comparisons depend on unwritten measurement choices, so v0.5 writes them down and pre-registers them |
| EleutherAI, [lm-evaluation-harness task guide](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/task_guide.md) and [multiple-choice normalisation](https://blog.eleuther.ai/multiple-choice-normalization/) | How option log-likelihoods are usually scored and normalised; the end-of-turn term and the normalisation over options are our choices, documented in [confidence methods](confidence-methods.md) |

## Judges and paired comparisons

| Source | What we took from it |
|---|---|
| Schenker & Gentleman, [*On Judging the Significance of Differences by Examining the Overlap Between Confidence Intervals*](https://www.tandfonline.com/doi/abs/10.1198/000313001317097960), The American Statistician 2001 | Overlapping intervals are a conservative test, so v0.5 uses paired differences on the same rows |
| McNemar, *Note on the sampling error of the difference between correlated proportions*, Psychometrika 1947 | The exact test of accuracy on discordant rows |
| Hanley & McNeil, Radiology 1982; DeLong, DeLong & Clarke-Pearson, Biometrics 1988 | Standard errors and comparison of correlated ROC curves; v0.5 uses a clustered paired bootstrap instead, which also handles repeated texts |
| Zheng et al., [*Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*](https://arxiv.org/abs/2306.05685), 2023; Zeng et al., [*LLMBar*](https://arxiv.org/abs/2310.07641), 2023 | LLM-as-judge practice and its biases; context for why confidence, not just agreement, is audited |
| [Laya](https://huggingface.co/convaiinnovations/laya) (Convai Innovations), code at v0.3.20 and its README | The adapter follows Laya's own code; its caveats (near chance zero-shot, token budgets, clamped temperatures, act head without signal) are quoted from the README |
| Public audit [Jev on BANKING77](https://github.com/simonmesmith/jev-banking77-experiment) | An existing accuracy audit on the same dataset, with no calibration; v0.5 adds the confidence side |
| [OpenEuroLLM/JudgeArena](https://github.com/OpenEuroLLM/JudgeArena), [atla-ai/judge-arena](https://github.com/atla-ai/judge-arena) | How other judge leaderboards are built; what we borrow and where v0.5 differs (committed raw evidence, pre-registration) |

## Datasets and labels

| Source | What we took from it |
|---|---|
| Casanueva et al., [*Efficient Intent Detection with Dual Sentence Encoders*](https://aclanthology.org/2020.nlp4convai-1.5/), NLP4ConvAI 2020 (BANKING77, CC BY 4.0) | The test split: 3,080 queries, 77 intents |
| Larson et al., [*An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction*](https://aclanthology.org/D19-1131/), EMNLP 2019 (CLINC150, CC BY 3.0) | The banking and credit-card domains plus the out-of-scope queries; the queries were written by crowd workers to a prompt |
| Ying & Thomas, [*Label Errors in BANKING77*](https://aclanthology.org/2022.insights-1.19/), Insights from Negative Results 2022 | About 14 % of the train split flagged as possibly mislabelled, found by automated detection. This is why v0.5 measures label noise with two blind annotators instead of assuming it |

## Tools and platform facts

| Source | What we took from it |
|---|---|
| [mlx-lm](https://github.com/ml-explore/mlx-lm) and [issue #259](https://github.com/ml-explore/mlx-lm/issues/259) | The MLX loading and caching API; the open report that prompt caching can change logits, which is why the self-check exists |
| [Claude Messages API reference](https://platform.claude.com/docs/en/api/messages/create) | No log-probability parameter |
| OpenAI developer forum on GPT-5 log-probabilities; a Google developer-forum thread on Gemini (community sources) | Reported absence of log-probabilities, checked per model with the smoke test before relying on it |
| Ollama v0.12.11 release notes | Log-probabilities from local models through an OpenAI-compatible API |
| Apple, [recommendedMaxWorkingSetSize](https://developer.apple.com/documentation/metal/mtldevice/recommendedmaxworkingsetsize) | How much unified memory the GPU can use, for sizing models on the Macs |

The full analysis behind these choices (a review of the v0.4 evidence, an external critique answered point by point, the plan with dates) is on the `docs/v05-analysis` branch.
