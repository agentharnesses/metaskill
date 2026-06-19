import pytest
import re
from pathlib import Path
from scripts.map_references import get_spec_description, build_tree


def test_get_spec_description_reads_frontmatter(tmp_path):
    f = tmp_path / "HARNESS.md"
    f.write_text("---\ndescription: Root harness\n---\nBody text\n")
    assert get_spec_description(f) == "Root harness"


def test_get_spec_description_falls_back_to_body(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("No frontmatter here, just body text.\n")
    assert get_spec_description(f) == "No frontmatter here, just body text."


def test_get_spec_description_skips_headings_in_body(tmp_path):
    f = tmp_path / "SKILLS.md"
    f.write_text("# Heading\n\nFirst real paragraph.\n")
    assert get_spec_description(f) == "First real paragraph."


def test_get_spec_description_returns_none_for_missing_file(tmp_path):
    assert get_spec_description(tmp_path / "nonexistent.md") is None


def test_get_spec_description_returns_none_for_empty_file(tmp_path):
    f = tmp_path / "empty.md"
    f.write_text("")
    assert get_spec_description(f) is None


def test_build_tree_single_harness_md(tmp_path):
    (tmp_path / "HARNESS.md").write_text("---\ndescription: Root harness\n---\n")
    node = build_tree(tmp_path, tmp_path)
    assert node is not None
    assert node["name"] == tmp_path.name
    assert len(node["specs"]) == 1
    assert node["specs"][0]["kind"] == "harness"
    assert node["specs"][0]["name"] == "HARNESS.md"
    assert node["specs"][0]["description"] == "Root harness"
    assert node["children"] == []


def test_build_tree_returns_none_for_empty_dir(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert build_tree(empty, tmp_path) is None


def test_build_tree_recurses_into_child_dirs(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    skills = tmp_path / "skills"
    skills.mkdir()
    auth = skills / "auth"
    auth.mkdir()
    (auth / "SKILL.md").write_text("---\ndescription: Auth skill\n---\n")

    node = build_tree(tmp_path, tmp_path)
    assert node is not None
    assert len(node["children"]) == 1
    skills_node = node["children"][0]
    assert skills_node["name"] == "skills"
    assert len(skills_node["children"]) == 1
    auth_node = skills_node["children"][0]
    assert auth_node["name"] == "auth"
    assert auth_node["specs"][0]["kind"] == "skill"
    assert auth_node["specs"][0]["description"] == "Auth skill"


def test_build_tree_prunes_empty_branches(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    empty = tmp_path / "no_specs_here"
    empty.mkdir()

    node = build_tree(tmp_path, tmp_path)
    child_names = [c["name"] for c in node["children"]]
    assert "no_specs_here" not in child_names


def test_build_tree_routing_file(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "SKILLS.md").write_text("---\ndescription: Skill index\n---\n")

    node = build_tree(skills, tmp_path)
    assert node is not None
    assert node["specs"][0]["kind"] == "routing"
    assert node["specs"][0]["description"] == "Skill index"


def test_build_tree_no_description_when_file_empty(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    node = build_tree(tmp_path, tmp_path)
    assert node is not None
    assert "description" not in node["specs"][0]
