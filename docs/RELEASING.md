# Releasing

Release branches, one per version, off `main`:

1. `git checkout -b release/vX.Y.Z main`. Bump `version` in `pyproject.toml` and `__version__` in `src/judge_audit/__init__.py`; add the section to `CHANGELOG.md`; update `docs/ROADMAP.md`.
2. PR `release/vX.Y.Z` → `main`; wait for CI (tests on 3.10–3.12, the exit-code contract, `verify_published.py`, dataset regeneration).
3. Squash-merge. Tag on `main`: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`, then move the floating tag the Action users reference: `git tag -f vX.Y && git push -f origin vX.Y`.
4. `release.yml` runs on the tag: builds sdist + wheel, checks the tag matches the version, attests build provenance (Sigstore), creates the GitHub release if it does not exist yet (generated notes you can edit), attaches the files, installs the built wheel in a clean job and smoke-tests it (`judge-audit --version` against the tag, a simulated `run`, `judge-audit-mcp --help`), generates and attaches an SBOM, and only then publishes to PyPI through Trusted Publishing. Any smoke-test failure fails the release before PyPI is touched.

   **SBOM.** `smoke` generates a CycloneDX 1.6 SBOM (`cyclonedx-py environment`, pinned `cyclonedx-bom==7.4.0`, a pip-installable tool rather than a marketplace action) from a clean virtual environment holding nothing but the built wheel plus its `mcp` extra, and uploads it to the GitHub release as `sbom.cdx.json`. It covers the Python packages the wheel and that extra pull in — `kunko-judge-audit` itself and, when the `mcp` extra is installed, the MCP SDK's dependency tree. It does **not** cover: the judges' hosted models (`claude-sonnet-4.5`, `llama-3.3-70b`, …) — they are audited subjects reached over an HTTP API, not Python dependencies, so an SBOM cannot and should not list them; the Node bridge under `src/judge_audit/judges/bridge/` (a separate `npm` tree, not part of the wheel); or the `charts`/`nli`/`anthropic` extras, which are optional and not installed for this smoke run. A consumer who installs additional extras has a different dependency set than this SBOM describes.
5. On the GitHub release page, tick **Publish this Action to the GitHub Marketplace** (UI only; the listing takes `action.yml`'s name, description and branding). Attach the launch videos (`docs/launch/brag.mp4`, `docs/launch/brag-vertical.mp4`; re-render per `docs/launch/README.md`) to the release and edit the notes. Delete the release branch.

Audits are not releases: a new audit (new checkpoint + report) lands through an `audit/*` branch and a normal PR, any time.

## One-time setup for PyPI (owner)

Trusted Publishing means no API token is stored anywhere: PyPI trusts the OIDC identity of this repo's `release.yml` running in the `pypi` environment.

1. On PyPI (2FA required), while the project does not exist yet, add a **pending publisher** at https://pypi.org/manage/account/publishing/: owner `kunko-ai-labs`, repository `judge-audit`, workflow `release.yml`, environment `pypi`.
2. In the repo: Settings → Environments → **New environment** `pypi`; restrict it to tags `v*` and require your review before deployment.
3. Push the tag. The first publish creates the project on PyPI under the pending publisher. The PyPI project is `kunko-judge-audit` (`judge-audit` was taken); the CLI and the import stay `judge-audit` / `judge_audit`.
