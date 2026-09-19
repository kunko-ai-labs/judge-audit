# Brag plan: judge-audit

Invocation: `/brag --tone polished --format landscape --duration 24` — voice off, music on, sfx on. Same house look as agent-assurance's launch film.

## Rubric

1. **What is the app?** A CLI that audits an AI judge's *calibration*: it runs the judge in shadow mode against decisions humans already made and reports whether the confidence it returns is honest (ECE), what share you could automate at zero observed errors, cost and p99, and a CI gate for drift. Every published number recomputes from a committed raw checkpoint.
2. **Most impressive claim:** "When it says 96 % confident, is it right 96 % of the time?" Supporting proof: the router audit — the same judge, same 120 tasks: 0/40 hard tasks routed right at median confidence 0.96 → 37/40 right after two descriptive sentences, with confidence that finally drops (0.59) when it is wrong.
3. **Visual hook:** a giant `96 %` that turns out to be `0 / 40`.
4. **Show from the actual UI:** the real CLI line `judge=jev n=120 accuracy=66.7% ece=0.3181`; the real "Read this first" lines from `docs/audit-jev-router.md`; the real ablation numbers from `docs/audit-jev-router-ablation.md`.
5. **Shortest satisfying video:** 24 s. Hook 4 s → the run 5 s → the verdict + reveal 8 s → three lines 4 s → outro 3 s.
6. **Tone:** `polished`. Quiet premium audit-tool film; restraint; terminal/monospace cards on near-black; one accent red for "confidently wrong", one green for "honest", one blue for keys.
7. **Audio:** the procedural bed `assets/music/judge-audit-bed.mp3` at ~0.35, fade in 0–1 s, fade out 22–24 s. SFX: one soft impact when the `0 / 40` lands, one error cue on the red verdict line, one soft bong on the final wordmark. Nothing else.
8. **Share caption:** see `share-copy.txt`.
9. **User flow:** the confident number → the shadow run → the verdict (confidently wrong) → the reveal (same judge, honest after the prompt fix) → what the tool is → install. Centerpiece = scene 3; poster frame = the `0 / 40 · 0.96` moment.

## Storyboard (24.0 s, 1920×1080)

| # | t | Scene | On screen | Motion | SFX |
|---|---|---|---|---|---|
| 1 | 0.0–4.0 | The hook | Kicker: "Your AI judge says". Giant `96 %` (mono, 260 px). Sub-line at 2.2 s: "confident." At 3.0 s a second line fades in under it: "Is it right 96 % of the time?" | `96 %` scales 0.96→1 over 0.6 s; lines rise 24 px and fade in; hold to 4.0. | — |
| 2 | 4.0–9.0 | The run | Terminal card. Typed prompt line: `$ judge-audit run tasks.jsonl --judge jev` (cursor-typed over 1.4 s). Output at 6.0 s, real copy: `judge=jev n=120 accuracy=66.7% ece=0.3181`. Caption at 7.0 s: "Shadow mode. Your humans already decided. The judge must match them." | Crossfade 0.7 s from scene 1. Output line rises in; `ece=0.3181` gets a red highlight at 6.6 s. | — |
| 3 | 9.0–17.0 | Verdict and reveal | Audit card, header "Read this first" (real). Line 1 (9.5 s): "Hard tasks routed to the cheap model: **40 / 40**". Line 2 (10.3 s): "Median confidence on those mistakes: **0.96**" — both red. Line 3 (11.2 s, muted): "= a coin glued to 'easy'. Accuracy 66.7 % is the constant-classifier baseline." At 13.0 s the card slides left and a second card slides in from the right, green: header "Same judge. Same 120 tasks. Two descriptive sentences on the options." · "**37 / 40** routed right" · "Confidence when wrong: **0.59**" · "Attack success: 0 / 40". Caption below both at 15.0 s: "The failure was the prompt. Only a calibration audit shows it." | Crossfade 0.7 s. Lines land 0.8 s apart, locked to beats; `0 / 40` hits with the impact; the red verdict line with the error cue. Second card slides 60 px with ease-out over 0.6 s. Hold to 17.0. | impactSoft (9.5 s), error_005 (10.3 s) |
| 4 | 17.0–21.0 | Three lines | One per beat (17.3 / 18.5 / 19.7): "Calibration, not accuracy." · "Every number from a committed raw checkpoint." · "Any judge: Jev, OpenJev, Claude, yours." Footer, muted: `ECE · zero-error coverage · cost · p99 · drift gate` | Crossfade 0.6 s; each line rises 24 px, fades in over 0.4 s. | — |
| 5 | 21.0–24.0 | Outro | Wordmark `judge-audit` (mono, 120 px) · tagline "When it says 90 %, is it right 90 % of the time?" · `pip install kunko-judge-audit` · small: `kunko-ai-labs/judge-audit · Apache-2.0` | Crossfade 0.7 s; wordmark scales 0.96→1 over 0.6 s; tagline at 21.7; install at 22.3. Hold. | bong_001 (21.2 s) |

Reading time check: every sentence ≤ 12 words; the two cards in scene 3 hold ≥ 2 s after their last line settles; longest hold is the reveal card (13.6–17.0).

## Vertical cut (1080×1920) for TikTok / Reels / Shorts

Same five scenes, same timing, same audio. Cards become 960 px wide and stack vertically; type sizes scale ×1.15; scene 3 stacks the two cards (red above, green below) instead of side by side; captions sit under the cards. Rendered from `composition-vertical/` with `data-duration="24"`.

## Handoff posture

/brag owns copy, angle, order, tone, audio selection. Hyperframes owns exact easings, transition mechanics, SFX timestamps and render.
