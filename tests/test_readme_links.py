"""The README is the PyPI page: nothing in it may be relative, and its YAML must parse.

A relative image or link is dead on pypi.org, and the Action snippet is copied into
workflows, so it must be valid YAML (an unquoted `${{ ... }}` inside a flow mapping is not).
"""
from __future__ import annotations

import re

import pytest

import judge_audit

yaml = pytest.importorskip("yaml")

TAG = f"v{judge_audit.__version__}"
PINNED = re.compile(
    r"^https://(?:github\.com/kunko-ai-labs/judge-audit/blob|"
    r"raw\.githubusercontent\.com/kunko-ai-labs/judge-audit)/" + re.escape(TAG) + r"/")


def references(md: str) -> list[str]:
    """Every link and image target the README carries, Markdown or HTML."""
    refs = re.findall(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", md)
    refs += re.findall(r'(?:src|srcset|href)="([^"]+)"', md)
    return refs


def relative_references(md: str) -> list[str]:
    return [r for r in references(md) if not re.match(r"(https?:|mailto:|#)", r)]


def yaml_blocks(md: str) -> list[str]:
    return re.findall(r"```ya?ml\n(.*?)```", md, flags=re.S)


@pytest.fixture(scope="module")
def readme(root):
    return (root / "README.md").read_text(encoding="utf-8")


def test_no_relative_link_or_image(readme):
    assert relative_references(readme) == []


def test_repository_files_are_pinned_to_this_release(readme):
    """Links to files in this repo use the tag of the version being published."""
    repo = [r for r in references(readme)
            if re.match(r"https://(github\.com/kunko-ai-labs/judge-audit/blob|"
                        r"raw\.githubusercontent\.com/kunko-ai-labs/judge-audit)/", r)]
    assert repo, "the README links to nothing in the repository"
    assert [r for r in repo if not PINNED.match(r)] == []


def test_every_pinned_target_exists_in_the_repository(readme, root):
    missing = []
    for ref in references(readme):
        m = PINNED.match(ref)
        if m:
            path = ref[m.end():].split("#", 1)[0]
            if not (root / path).exists():
                missing.append(path)
    assert missing == []


def test_the_launch_video_is_a_release_asset_that_exists(readme):
    assert "releases/latest/download" not in readme
    assert "releases/download/v0.5.1/judge-audit-launch.mp4" in readme


def test_every_yaml_snippet_parses(readme):
    blocks = yaml_blocks(readme)
    assert blocks, "the README has a workflow snippet"
    for block in blocks:
        assert yaml.safe_load(block)


def test_the_action_snippet_passes_the_key_as_a_string(readme):
    step = yaml.safe_load(next(b for b in yaml_blocks(readme) if "judge-audit@" in b))[0]
    assert step["env"]["AI_GATEWAY_API_KEY"] == "${{ secrets.AI_GATEWAY_API_KEY }}"


def test_the_quickstart_clones_the_repo_before_using_its_examples(readme):
    quick = readme.split("## Quickstart", 1)[1].split("```", 2)[1]
    assert quick.index("git clone") < quick.index("examples/")


@pytest.mark.parametrize("bad", ["[x](docs/a.md)", "![x](docs/a.png)", '<img src="docs/a.png">',
                                 '<source srcset="docs/a.png">'])
def test_the_check_notices_a_relative_reference(bad):
    assert relative_references(bad)


def test_the_check_notices_an_unquoted_expression_in_a_flow_mapping():
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load("env: { K: ${{ secrets.K }} }")
