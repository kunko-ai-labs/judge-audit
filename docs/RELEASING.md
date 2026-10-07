# Releasing

Release branches, one per version, off `main`:

1. `git checkout -b release/vX.Y.Z main`. Bump `version` in `pyproject.toml` and `__version__` in `src/judge_audit/__init__.py`; add the section to `CHANGELOG.md` (a version under development reads `— unreleased (dated when tagged)`; this PR replaces that with the day you will tag, and drops the README's `# resolves once vX.Y.0 is tagged` comment on the Action snippet); update `docs/ROADMAP.md`.
2. PR `release/vX.Y.Z` → `main`; wait for CI (tests on 3.10–3.12, the exit-code contract, `verify_published.py`, dataset regeneration, CodeQL) and for the review described in [CONTRIBUTING.md § Review](../CONTRIBUTING.md#review). Branch protection does not require a GitHub approving review — this is a single-maintainer repository and an author cannot approve their own PR — so that review is a process, not a GitHub gate.
3. Squash-merge. Tag on `main`: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`, then move the floating tag the Action users reference: `git tag -f vX.Y && git push -f origin vX.Y`. `vX.Y` is a lightweight tag and only moves forward along `main`; the `release-tags` ruleset rejects any other move. The README's `uses: kunko-ai-labs/judge-audit@vX.Y` snippet resolves only from this step on.
   After the merge, run `bash scripts/protect_main.sh` (idempotent) so `main`'s branch protection and the `release-tags` ruleset match what the script and CONTRIBUTING.md describe.
4. `release.yml` runs on the tag, in four jobs, each only after the previous one passed:
   `build` builds sdist + wheel and checks the tag matches the version; `smoke` installs the built wheel in a clean runner and smoke-tests it (`judge-audit --version` against the tag, a simulated `run`, `judge-audit-mcp --help`), then generates and checks the SBOM; `github-release` attests the build provenance of the wheel, the sdist and the SBOM (Sigstore), creates the GitHub release if it does not exist yet (generated notes you can edit) and attaches the three files; `publish` publishes to PyPI through Trusted Publishing. A smoke-test failure therefore stops the release before anything is attested, attached to GitHub or sent to PyPI. Only jobs that install nothing (`github-release`, `publish`) hold an OIDC token (`id-token: write`): `build` and `smoke` pip-install packages that are not all hash-pinned, and a compromised one must not be able to sign an attestation or publish.

   **SBOM.** `smoke` generates a CycloneDX 1.6 SBOM with `cyclonedx-py environment` — a pip-installable tool rather than a marketplace action, pinned with hashes in `.github/sbom-requirements.txt` (`cyclonedx-bom==7.4.0` and its dependencies, installed with `--require-hashes`) — from a virtual environment created `--without-pip` that holds nothing but the built wheel plus its `mcp` extra. Its root component is `kunko-judge-audit` at the tagged version (read from `pyproject.toml`, which the `build` job has already checked against the tag), and a workflow step fails the release if the root is anything else or if `pip` or the SBOM tool leaked into the component list. `github-release` attests the SBOM file with the same `actions/attest-build-provenance` action as the wheel (`gh attestation verify sbom.cdx.json --repo kunko-ai-labs/judge-audit`) and attaches it to the GitHub release as `sbom.cdx.json`. It covers the Python packages the wheel and its `mcp` extra pull in. It does **not** cover: the judges' hosted models (`claude-sonnet-4.5`, `llama-3.3-70b`, …) — they are audited subjects reached over an HTTP API, not Python dependencies, so an SBOM cannot and should not list them; the npm dependencies of the Node bridge (`judge_audit/judges/bridge/` ships its `package.json` and `package-lock.json` in the wheel, but the packages themselves are fetched by `npm install` when you set up the Jev bridge, outside the Python environment); or the `charts`/`nli`/`anthropic` extras, which are optional and not installed for this smoke run. A consumer who installs additional extras has a different dependency set than this SBOM describes.
5. On the GitHub release page, tick **Publish this Action to the GitHub Marketplace** (UI only; the listing takes `action.yml`'s name, description and branding). Edit the notes: what changed for a user, the headline findings with their caveats, how to verify the build. Delete the release branch.

## Pre-releases (`vX.Y.ZrcN`, `aN`, `bN`)

A pre-release follows steps 1, 2 and 4 above, with the PEP 440 version (`0.6.0rc1`) in `pyproject.toml` and `__version__`, and the tag `v0.6.0rc1` on `main`. It differs in four places:

- **Contents.** Only what is already on `main`, reviewed and tested. A pre-release on PyPI can be yanked but never replaced, so a fix is a new `rcN+1`.
- **GitHub release.** `release.yml` detects the suffix (`a`, `b` or `rc` followed by a number; `.postN` is a final release; a `.devN` tag is refused by `build` and never published) and marks the release as a pre-release, never Latest. It does so also when the release was created by hand before the tag.
- **No floating tag, no Marketplace.** Do not move `vX.Y` for a pre-release: the README snippet and Action users stay on the last final release. Do not tick **Publish this Action to the GitHub Marketplace**. Do not change the README's `@vX.Y` Action snippet until the final release.
- **PyPI.** The same Trusted Publishing path and the same `pypi` environment approval by the maintainer. `pip install kunko-judge-audit` keeps resolving to the last final release; a pre-release installs only when pinned (`==0.6.0rc1`) or with `--pre`.

Verify a pre-release as a final one: `pip install kunko-judge-audit==X.Y.ZrcN`, `judge-audit --version`, and `gh attestation verify <wheel> --repo kunko-ai-labs/judge-audit`.

Audits are not releases: a new audit (new checkpoint + report) lands through an `audit/*` branch and a normal PR, any time.

## One-time setup for PyPI (owner)

Trusted Publishing means no API token is stored anywhere: PyPI trusts the OIDC identity of this repo's `release.yml` running in the `pypi` environment.

1. On PyPI (2FA required), while the project does not exist yet, add a **pending publisher** at https://pypi.org/manage/account/publishing/: owner `kunko-ai-labs`, repository `judge-audit`, workflow `release.yml`, environment `pypi`.
2. In the repo: Settings → Environments → **New environment** `pypi`; restrict it to tags `v*` and require your review before deployment.
3. Push the tag. The first publish creates the project on PyPI under the pending publisher. The PyPI project is `kunko-judge-audit` (`judge-audit` was taken); the CLI and the import stay `judge-audit` / `judge_audit`.
