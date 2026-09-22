# Hyperframes Composition Brief: judge-audit

## Objective
Create a short launch-style brag video for judge-audit, in the house style of agent-assurance's launch film.

## Output
- Composition directories: `docs/launch/composition/` (1920×1080) and `docs/launch/composition-vertical/` (1080×1920)
- Rendered videos: `docs/launch/brag.mp4`, `docs/launch/brag-vertical.mp4`; poster `docs/launch/brag.jpg` (t = 10.5 s)
- Duration: 24 seconds

## Source Material
- Project root: the `judge-audit` repository (every path below is relative to it)
- Primary files read: README.md, docs/audit-jev-router.md, docs/audit-jev-router-ablation.md, docs/audit-jev-router.json, docs/audit-jev-router-described.json
- Product name: judge-audit
- Tagline / strongest claim: "When it says 96 % confident, is it right 96 % of the time?"
- Real copy to show verbatim: `judge=jev n=120 accuracy=66.7% ece=0.3181` · `Hard tasks routed to the cheap model: 40 / 40` · `Median confidence on those mistakes: 0.96` · `37 / 40 routed right` · `Confidence when wrong: 0.59` · `Attack success: 0 / 40`

## Creative direction
- Tone: polished. Quiet premium audit-tool film. Restraint as the choice.
- Palette: background #0b0f14, surface #131a22 / #161b22, text #e6edf3, muted #8b98a5, accent red #f85149 (confidently wrong), accent green #3fb950 (honest), accent blue #79c0ff (keys).
- Typography: system UI sans for headings (light-to-medium weight), Menlo/Monaco/Consolas/monospace for the terminal, the wordmark and the install line. No external fonts.
- Transitions: slow crossfade 0.6–0.8 s between scenes; the reveal card in scene 3 slides in (left→right in landscape, bottom→top in vertical).

## Storyboard
See `brag-plan.md` (5 scenes, 24.0 s). Scene 3 (verdict → reveal) is the centerpiece; the poster frame is the `40 / 40 · 0.96` moment before the reveal.

## Audio
- Audio arc: warm bed enters under the hook, holds under the run, the `40 / 40` lands with a soft impact and the `0.96` line with one dry error cue, the bed thins under the three lines and fades out under the wordmark with a single soft bong.
- Music: `assets/music/judge-audit-bed.mp3` (procedural, generated for Kunko AI Labs).
- Music treatment: volume 0.35, fade in 0–1.0 s, fade out 22.0–24.0 s via `data-automation` volume lane.
- Audio-coupled moments: `40 / 40` (9.5 s) — impactSoft_medium_000; `0.96` (10.3 s) — error_005; wordmark (21.2 s) — bong_001.
- Audio-reactive treatment: none.

## Hyperframes Instructions
Follow `hyperframes-core` (one paused GSAP timeline registered as `window.__timelines["main"]`, `data-start`/`data-duration` on every clip, `class="clip"`, no CSS transform + GSAP conflict, every `<audio>` with an id, no `<br>` in body text, deterministic only) and `hyperframes-cli` (`npx hyperframes check` as the single gate, then `render --quality delivery`).

Requirements:
- Show real CLI output and real audit numbers (scenes 2–3 are verbatim from the published reports).
- Keep all text readable; WCAG contrast must pass `check`.
- 24 seconds exactly (`data-duration="24"` on the root).
- Music + three SFX as above.
