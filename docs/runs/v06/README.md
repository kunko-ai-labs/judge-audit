# v0.6 study: run record

**Plan:** frozen before the first study call; sha256 `aef725edbaa078e0c3956757709e95ae1ce01364d72451df9c7d1e7bc35863b6` in [`docs/v06-plan.sha256`](../../v06-plan.sha256), commit `43e7e1e06125350311ab8cb1b1d8e9d1d81ab9a4` tagged `v06-plan-freeze`. The text is published at the release as `docs/v06-plan.md`. Amendments after the freeze have their sha256 in [`docs/v06-amendments.sha256`](../../v06-amendments.sha256), each committed before the call it governs; their texts are published with the plan.

**Code:** every run below used judge-audit at `43e7e1e06125350311ab8cb1b1d8e9d1d81ab9a4`, the commit tagged `v06-plan-freeze` (checkpoint headers record the package version only, so the commit is named here). `unsloth-decision-4b` ran through a runner outside this repository that installs judge-audit at that commit and writes standard checkpoints (pilot record §7).

**Data:** `examples/massive/labels-test-<locale>.jsonl`, MASSIVE 1.1 test, 2,974 items per locale; each header records the file's sha256. Results are computed by `scripts/v06_study.py` into `docs/v06/`; this file reports no accuracy or calibration figure.

## Checkpoints

| judge | role | locale | rows | first call (header, UTC) | recorded cost | ceiling (`max_usd`) | sha256 |
|---|---|---|---:|---|---:|---:|---|
| `jev` | primary | `en-US` | 2,974 | 2026-10-12T20:04:32+00:00 | $0.0984 | 0.186226 | `22a2b3ac359d0162e289873a64ffca7b6979c542b49418b76b2720370c4bc0e5` |
| `jev` | primary | `es-ES` | 2,974 | 2026-10-12T19:27:17+00:00 | $0.0986 | 0.383708 | `7a393cef730c29cc66bbd9623fc078d655ff47608f3dbc64abad466c1fe43d79` |
| `jev` | primary | `ca-ES` | 2,974 | 2026-10-12T19:49:38+00:00 | $0.0989 | 0.285107 | `df1dfc30950a0a74e8133e3e1605ca472c64fb5ea1cfdafbf2b4df95e98aa37c` |
| `gpt-6-luna` | primary | `en-US` | 2,974 | 2026-10-12T19:24:42+00:00 | $0.2080 | 1.0 | `f77d74ac296a396737eb9b5dd5e878d1c1bc3e5fd23ab17874dbc933b485f8cd` |
| `gpt-6-luna` | primary | `es-ES` | 2,974 | 2026-10-12T20:38:11+00:00 | $0.2094 | 0.792018 | `fbf42f31a02aec5af54b247e0ef1c092b0fb015cd553e14c0267d49bd79f8c44` |
| `gpt-6-luna` | primary | `ca-ES` | 2,974 | 2026-10-12T20:55:59+00:00 | $0.2099 | 0.582597 | `6e0d5372b917c40dfdb831fe5bb71c700c8a9f767e752101c9e2e7fcb6915c36` |
| `claude-sonnet-4.5` | primary | `en-US` | 2,974 | 2026-10-12T21:18:34+00:00 | $8.0728 | 39.0 | `991a50f847fb9dd5546ec3866eb801fb4b3ed04282aa3ce926cbb1724cd36ed6` |
| `claude-sonnet-4.5` | primary | `es-ES` | 2,974 | 2026-10-12T23:27:08+00:00 | $8.7341 | 30.927216 | `1e66b4743085d0491d05029ebe9b1dbdc793189e413e8f0cdec2391a49e674ac` |
| `claude-sonnet-4.5` | primary | `ca-ES` | 2,974 | 2026-10-13T01:52:24+00:00 | $9.2344 | 22.193088 | `6b21c1c27c1a785c4cf31ff91a24d4cad9ad58e91401d8f522b4591dec3cec32` |
| `decision2-kai-0.6b` | exploratory | `en-US` | 2,974 | 2026-10-12T18:54:23+00:00 | $0.0000 | — | `a3c102c5b0b6c2fa294ca4c9d2cbfa7f0853b50035469e06c978bfbaedd03d76` |
| `decision2-kai-0.6b` | exploratory | `es-ES` | 2,974 | 2026-10-12T20:03:14+00:00 | $0.0000 | — | `12fe57761d34f9e98271de17b64041339bd272ff89175e9b9b2556ea545dfb8f` |
| `decision2-kai-0.6b` | exploratory | `ca-ES` | 2,974 | 2026-10-12T21:06:38+00:00 | $0.0000 | — | `322b6d7411940be1a0521c5ebf011f671a248a78d30ad7cf5c432caad8ba5836` |
| `laya-multilingual` | exploratory | `en-US` | 2,974 | 2026-10-13T01:19:54+00:00 | $0.0000 | — | `c0e63a8204dab02a3f8dda546cfacf79efa8be8aa307281eabd9e59c406ef13c` |
| `laya-multilingual` | exploratory | `es-ES` | 2,974 | 2026-10-13T01:22:29+00:00 | $0.0000 | — | `e167559d24925e39e321b286fde96c1cb2b3511334f44aa59efad55fbf1faebc` |
| `laya-multilingual` | exploratory | `ca-ES` | 2,974 | 2026-10-13T01:25:07+00:00 | $0.0000 | — | `683f963a98692db7d224f62554c6797a6b6aa98aa9381f2eba2ab35b63664140` |
| `gemini-3.6-flash` | exploratory | `en-US` | 2,974 | 2026-10-13T04:27:11+00:00 | $1.8961 | 5.0 | `32cf2ebc958a2da0a4d90aacb11daa13597ba9d808bdf5ab544aea89c6552f44` |
| `gemini-3.6-flash` | exploratory | `es-ES` | 2,974 | 2026-10-13T06:10:41+00:00 | $1.9495 | 3.103947 | `68f0cd76d6ef57a941c76aa4023dd9f3f48053d91ae9027a45b88e9788091a7b` |
| `gemini-3.6-flash` | exploratory | `ca-ES` | 2,974 | 2026-10-13T08:03:52+00:00 | $1.9002 | 5.154445 | `70e6cfef46aea2f3fb3ae8fc1109d96f8dc708d476fb81a6d78612c282c189f5` |
| `deepseek-r1` | exploratory | `en-US` | 2,974 | 2026-10-13T10:34:30+00:00 | $7.4120 | 34.0 | `811853b15cfa7da86a1069f7ada8c84fbc788f3a1ce55486bf937661503a2868` |
| `deepseek-r1` | exploratory | `es-ES` | 2,974 | 2026-10-13T13:24:51+00:00 | $7.7147 | 26.588039 | `9faa8afe5ba0a848ba84ad7ac8a8603199edb671fbdb6062573817b4c88aa8b8` |
| `deepseek-r1` | exploratory | `ca-ES` | 2,974 | 2026-10-13T16:29:19+00:00 | $7.6644 | 18.873337 | `813bb62345cd39e9ee9165e1e03752c4e15189a4c5c2d4f00a02d2d5107b5dd9` |
| `clef-flash` | exploratory | `en-US` | 2,974 | 2026-10-13T07:37:36+00:00 | $0.2659 | 1.0 | `fe575b5eaf39deb31c788474cec41aa24ac43211d0feac102bd9c74db164d90e` |
| `clef-flash` | exploratory | `es-ES` | 2,974 | 2026-10-13T08:07:49+00:00 | $0.2663 | 0.734119 | `66661095998c3cec8686bed48edb8e38334200cfd2a7a2317c6ab5135b3b7e20` |
| `clef-flash` | exploratory | `ca-ES` | 2,974 | 2026-10-14T08:32:35+00:00 | $0.2669 | 0.467798 | `6c760c6361ded3b466bf67a36341a2144697fc5a70099d46d48d36246cc184e0` |
| `decider-2b` | exploratory | `en-US` | 2,974 | 2026-10-12T22:07:04+00:00 | $0.0000 | — | `27c12e58c567b6eade061eb4a1a67cad7ae502dfd5e4b9a705a6cfaac2cb8702` |
| `decider-2b` | exploratory | `es-ES` | 2,974 | 2026-10-12T22:38:17+00:00 | $0.0000 | — | `32a23e144142b862cbcb7c078fbbe5756e3f181d9a092ae16efbd2caf51da28b` |
| `decider-2b` | exploratory | `ca-ES` | 2,974 | 2026-10-12T23:09:33+00:00 | $0.0000 | — | `fc856702d04d02f6faea332e358d5357c936f31529982cd20c604c1ca12dd94f` |
| `strands-decider-2b` | exploratory | `en-US` | 2,974 | 2026-10-12T23:41:06+00:00 | $0.0000 | — | `8417a4c30edce9e1e52492109774dea4e000d94ec563c895d9f7cbebc859c21a` |
| `strands-decider-2b` | exploratory | `es-ES` | 2,974 | 2026-10-13T00:13:48+00:00 | $0.0000 | — | `5f682f44178f8b54d3a44f4487e7578768c49e50663b8cdca08fbc1a159944db` |
| `strands-decider-2b` | exploratory | `ca-ES` | 2,974 | 2026-10-13T00:46:27+00:00 | $0.0000 | — | `b44f6605acb590fe080cab60d327bf7e31b77f3bd463e696b998c35760245168` |
| `microsoft-decision-1` | exploratory | `en-US` | 2,974 | 2026-10-13T09:20:34+00:00 | $0.0490 | 0.5 | `870a519be675624bc36a5fbf704d28700071377aed354757f282b630751e3f49` |
| `microsoft-decision-1` | exploratory | `es-ES` | 2,974 | 2026-10-13T09:46:20+00:00 | $0.0492 | 0.450994 | `f742074f63ce7def577b5ab29eb01f5536313a32e737665bc1eb58f9f86b6926` |
| `microsoft-decision-1` | exploratory | `ca-ES` | 2,974 | 2026-10-13T10:10:15+00:00 | $0.0495 | 0.401782 | `0c760fd3c92eaa59c1c4cdd8841ade9d46d736ae14895c96005958a8f07a4a6d` |
| `unsloth-decision-4b` | exploratory | `en-US` | 2,974 | 2026-10-13T07:44:41+00:00 | $0.0000 | — | `a0a4706bb37f0d4993ed06f873c5fb3e699175a47fe1d393b30d98d81757a296` |
| `unsloth-decision-4b` | exploratory | `es-ES` | 2,974 | 2026-10-13T08:37:23+00:00 | $0.0000 | — | `6357aece380126e412de5214ea663b80d2fd4fff16ff31cd4b2fb1c9204309c3` |
| `unsloth-decision-4b` | exploratory | `ca-ES` | 2,974 | 2026-10-13T09:29:50+00:00 | $0.0000 | — | `e3633c52e2fda7fb7af5d0dbcd59e6974e5f57324d548d39f46bd68fb2533d36` |

**Kept, never used for any figure:**

- `jev-en-US.ckpt.duplicate-writes.jsonl`: 3,516 row lines, 2,974 distinct rows, recorded cost $0.1163, sha256 `541587e3f0b1660c21196b2145dec34e42a315c070c4860ae9e5f3c19f43428c` (amendment A1).

**Recorded cost of the study:** $56.5644, every checkpoint above included, against the $115 budget. Recorded cost can be below a provider's bill (pricing multipliers, reasoning tokens).

## Run notes

Times are UTC, from 2026-10-12. Results were seen before the study ended. One driver log line with Laya multilingual's `en-US` accuracy was seen while fixing that run's settings (amendment A4). The analysis of the other eleven judges was run and read on 2026-10-13, before Clef-flash `es-ES` and `ca-ES` completed. Clef-flash's route, model id, settings and ceilings were those fixed before its first call. Paid usage on its route was enabled on 2026-10-14, after that analysis had been read; it changed how the route is billed, not the model, route, settings, rows or ceilings. No setting of any run was changed after a result was seen.

- **Amendment A1 (Jev `en-US`, double write).** The hosted-run script was started twice (19:09:34Z and 19:21:03Z on 2026-10-12). From row 2266 both copies appended the same rows to the Jev `en-US` checkpoint, until the second stopped at 19:23:40Z; 542 rows were written twice. That file is kept unchanged as `jev-en-US.ckpt.duplicate-writes.jsonl` and is used for no figure. Jev `en-US` was rerun from row 0 after Jev `es-ES` and `ca-ES` completed; the rerun's ceiling was Jev's $0.50 minus every other Jev checkpoint's recorded cost, the incident file included.
- **Amendment A2 (erratum to A1; order of runs).** When the first copy finished `en-US` (19:24:41Z), the driver wrote its usual report files from the double-written checkpoint, outside the repository. Nobody opened them; they were deleted unread at about 19:37Z after recording their sha256 (stated in A2; not recomputable, since the files are gone). The first copy's Jev `es-ES` and `ca-ES` runs exited at argument parsing with no call (a ceiling with more than 6 decimals), and it was stopped during `gpt-6-luna` `en-US` at about 19:25:41Z with 135 rows, later resumed. A second script ran Jev `es-ES` from 19:27:17Z and was stopped with 1,975 rows (A2 gives 19:36:58Z, when the stop was issued; the checkpoint's last write was 19:36:56Z), later resumed under the ceiling in its header. From A2 on, a judge's next locale starts only when the previous checkpoint holds all 2,974 rows, and one lock prevents two copies.
- **Amendment A3 (gemini-3.6-flash ceiling; parallel judges).** gemini-3.6-flash's ceiling was set again by the plan's rule on its measured `en-US` rate: $9 instead of the estimated $5 (ceilings $85 of $115). From 2026-10-13 two copies of the run script ran different judges at once, one lock per judge.
- **Laya multilingual.** Two starts failed while loading the model, before any request: the first with the model hub offline, the second with the default model id instead of `convaiinnovations/laya-multilingual`. Neither wrote a checkpoint. The third start ran with the pilot's settings.
- **unsloth-decision-4b.** The first hosted-notebook session lost its runtime after the parity check and before any study call (no checkpoint). The study ran in a new session on the same GPU type (recorded in each header), at the freeze commit, with parity within tolerance and the adapter's answers equal to direct `predict` calls on the rows checked (`unsloth-decision-4b.checks.json`).
- **Clef-flash.** Its hosted route has a daily free allocation. `es-ES` stopped at row 462 on 2026-10-13 when the allocation ran out (no answer recorded for the failed request). On 2026-10-14 the resumed run's retries at row 462 were refused again (no row recorded), and the run was stopped. Paid usage was then enabled on the same account and key. The run resumed from the same checkpoint at 08:14Z on the same route, model id and settings, with each language's ceiling unchanged. It completed `es-ES` and `ca-ES` (2,974 rows each, no row without an answer). Every row before and after row 462 reports the same served model (`raw.served.model` = `clef-flash`). The recorded cost for the three languages is $0.80, under the judge's $1 ceiling.
- **No served model id.** The routes used for claude-sonnet-4.5 (primary) and deepseek-r1 report no served model id (`raw.served.model` is null on every row), so a change of served model cannot be detected for these two judges.
- **gpt-6-luna refusals.** The Decisions API refused 34 `en-US`, 20 `es-ES` and 20 `ca-ES` requests (`raw.refusal`); each is a row without a usable answer (`no_answer`: no decision, no confidence), counted against the judge (plan, rows without a usable answer). One fell among the first 40 `en-US` rows, under the 5 % stop rule.
- **Order of runs (deviation in timing only).** The plan runs local models first, then hosted ones. The local runs (first header 18:54:23Z on 2026-10-12, Kai `en-US`) and the hosted runs (first header 19:09:34Z or later) ran at the same time instead. No setting, row or ceiling changed; no amendment was written for this before the calls, so it is recorded here as a deviation.
