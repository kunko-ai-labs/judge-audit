# Releasing

Release branches, one per version, off `main`:

1. `git checkout -b release/vX.Y.Z main`. Bump `version` in `pyproject.toml` and `__version__` in `src/judge_audit/__init__.py`; add the section to `CHANGELOG.md`; update `docs/ROADMAP.md`.
2. PR `release/vX.Y.Z` → `main`; wait for CI (tests on 3.10–3.12, the exit-code contract, `verify_published.py`, dataset regeneration).
3. Squash-merge. Tag on `main`: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`, then move the floating tag: `git tag -f vX.Y && git push -f origin vX.Y`.
4. `release.yml` runs on the tag: builds sdist + wheel, checks the tag matches the version, attests build provenance (Sigstore), creates the GitHub release if it does not exist yet (generated notes you can edit), attaches the files, and publishes to PyPI through Trusted Publishing.
5. Attach the launch video (`docs/demo.mp4`, regenerated from the tape with `ffmpeg`) to the release and edit the notes. Delete the release branch.

Audits are not releases: a new audit (new checkpoint + report) lands through an `audit/*` branch and a normal PR, any time.

## One-time setup for PyPI (owner)

Trusted Publishing means no API token is stored anywhere: PyPI trusts the OIDC identity of this repo's `release.yml` running in the `pypi` environment.

1. On PyPI (2FA required), while the project does not exist yet, add a **pending publisher** at https://pypi.org/manage/account/publishing/: owner `kunko-ai-labs`, repository `judge-audit`, workflow `release.yml`, environment `pypi`.
2. In the repo: Settings → Environments → **New environment** `pypi`; restrict it to tags `v*` and require your review before deployment.
3. Push the tag. The first publish creates the project on PyPI under the pending publisher.
