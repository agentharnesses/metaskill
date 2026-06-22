import pytest
from pathlib import Path
from scripts.disclose import (
    parse_frontmatter,
    should_skip,
    classify,
    detect_leaf_type,
    load_leaf_detectors,
    file_type,
    get_description,
    peek,
    _detector_cache,
)


def test_parse_frontmatter_with_description():
    text = "---\nname: foo\ndescription: A test skill\n---\nBody content"
    meta, body = parse_frontmatter(text)
    assert meta["description"] == "A test skill"
    assert body == "Body content"


def test_parse_frontmatter_quoted_value():
    text = '---\ndescription: "Quoted value"\n---\n'
    meta, _ = parse_frontmatter(text)
    assert meta["description"] == "Quoted value"


def test_parse_frontmatter_no_frontmatter():
    text = "Just body content"
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == "Just body content"


def test_parse_frontmatter_incomplete():
    text = "---\nname: foo\n"
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_should_skip_hidden(tmp_path):
    f = tmp_path / ".hidden"
    f.touch()
    assert should_skip(f, tmp_path) is True


def test_should_skip_harness_md(tmp_path):
    f = tmp_path / "HARNESS.md"
    f.touch()
    assert should_skip(f, tmp_path) is True


def test_should_skip_own_summary(tmp_path):
    # When peeking a dir named "skills", SKILLS.md inside it is skipped
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skills_md = skills_dir / "SKILLS.md"
    skills_md.touch()
    assert should_skip(skills_md, skills_dir) is True


def test_should_not_skip_regular_file(tmp_path):
    f = tmp_path / "schema.md"
    f.touch()
    assert should_skip(f, tmp_path) is False


def test_should_not_skip_regular_dir(tmp_path):
    d = tmp_path / "myskill"
    d.mkdir()
    assert should_skip(d, tmp_path) is False


def test_classify_skill(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")
    d = tmp_path / "myskill"
    d.mkdir()
    (d / "SKILL.md").touch()
    assert classify(d) == "skill"


def test_classify_group(tmp_path):
    d = tmp_path / "mygroup"
    d.mkdir()
    assert classify(d) == "group"


def test_classify_file(tmp_path):
    f = tmp_path / "ref.md"
    f.touch()
    assert classify(f) == "file"


# ── detect_leaf_type ─────────────────────────────────────────────────────────

def test_detect_leaf_type_config_skill(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")
    d = tmp_path / "my-skill"
    d.mkdir()
    (d / "SKILL.md").touch()
    assert detect_leaf_type(d) == "skill"


def test_detect_leaf_type_config_custom(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("mcp-server=MCP-SERVER.md\n")
    d = tmp_path / "my-server"
    d.mkdir()
    (d / "MCP-SERVER.md").touch()
    assert detect_leaf_type(d) == "mcp-server"


def test_detect_leaf_type_config_no_match(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")
    d = tmp_path / "plain"
    d.mkdir()
    assert detect_leaf_type(d) is None


def test_detect_leaf_type_no_config_returns_none(tmp_path):
    d = tmp_path / "my-skill"
    d.mkdir()
    (d / "SKILL.md").touch()
    assert detect_leaf_type(d) is None


def test_detect_leaf_type_explicit_harnessleaf(tmp_path):
    d = tmp_path / "my-server"
    d.mkdir()
    (d / ".harnessleaf").write_text("mcp-server\n")
    assert detect_leaf_type(d) == "mcp-server"


def test_detect_leaf_type_explicit_wins_over_structural(tmp_path):
    d = tmp_path / "tricky"
    d.mkdir()
    (d / "SKILL.md").touch()
    (d / ".harnessleaf").write_text("mcp-server")
    assert detect_leaf_type(d) == "mcp-server"


def test_load_leaf_detectors_parses_key_value(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\nmcp-server=MCP-SERVER.md\n")
    result = load_leaf_detectors(tmp_path)
    assert result == {"skill": "SKILL.md", "mcp-server": "MCP-SERVER.md"}


def test_load_leaf_detectors_ignores_comments_and_blanks(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("# comment\n\nskill=SKILL.md\n")
    result = load_leaf_detectors(tmp_path)
    assert result == {"skill": "SKILL.md"}


def test_load_leaf_detectors_returns_none_when_absent(tmp_path):
    assert load_leaf_detectors(tmp_path) is None


def test_load_leaf_detectors_finds_ancestor(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")
    subdir = tmp_path / "a" / "b"
    subdir.mkdir(parents=True)
    result = load_leaf_detectors(subdir)
    assert result == {"skill": "SKILL.md"}


def test_detect_leaf_type_none_for_plain_group(tmp_path):
    d = tmp_path / "group"
    d.mkdir()
    assert detect_leaf_type(d) is None


def test_classify_custom_leaf_type(tmp_path):
    d = tmp_path / "my-server"
    d.mkdir()
    (d / ".harnessleaf").write_text("mcp-server")
    assert classify(d) == "mcp-server"


def test_get_description_custom_leaf_type(tmp_path):
    d = tmp_path / "my-server"
    d.mkdir()
    (d / "MCP-SERVER.md").write_text("---\ndescription: Runs the MCP server\n---\n")
    assert get_description(d, "mcp-server") == "Runs the MCP server"


def test_file_type_in_subfolder(tmp_path):
    f = tmp_path / "references" / "schema.md"
    f.parent.mkdir()
    f.touch()
    assert file_type(f, tmp_path) == "references"


def test_file_type_at_root(tmp_path):
    f = tmp_path / "readme.md"
    f.touch()
    assert file_type(f, tmp_path) == tmp_path.name


def test_get_description_from_frontmatter(tmp_path):
    skill_dir = tmp_path / "myskill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\ndescription: Does the thing\n---\nBody")
    assert get_description(skill_dir, "skill") == "Does the thing"


def test_get_description_fallback_to_body(tmp_path):
    skill_dir = tmp_path / "myskill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: foo\n---\n# Heading\nFirst real line")
    assert get_description(skill_dir, "skill") == "First real line"


def test_get_description_missing_file(tmp_path):
    d = tmp_path / "ghost"
    d.mkdir()
    assert get_description(d, "skill") is None


def test_peek_mixed_directory(tmp_path):
    root = tmp_path
    (root / ".leaf-detectors").write_text("skill=SKILL.md\n")

    # A skill dir
    skill = root / "my-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\ndescription: My skill\n---\n")

    # A group dir
    group = root / "subgroup"
    group.mkdir()
    (group / "SUBGROUP.md").write_text("---\ndescription: A subgroup\n---\n")

    # A reference file
    ref = root / "notes.md"
    ref.write_text("---\ndescription: Some notes\n---\n")

    # Should be skipped
    (root / "HARNESS.md").touch()
    (root / ".hidden").touch()

    items = peek(root, root)

    types = [i["type"] for i in items]
    names = [i["name"] for i in items]

    assert "skill" in types
    assert "group" in types
    assert "my-skill" in names
    assert "subgroup" in names
    assert "notes.md" in names
    assert "HARNESS.md" not in names
    assert ".hidden" not in names


def test_peek_items_have_ids(tmp_path):
    (tmp_path / "a-skill").mkdir()
    ((tmp_path / "a-skill") / "SKILL.md").touch()
    items = peek(tmp_path, tmp_path)
    assert items[0]["id"] == 1


def test_peek_dirs_before_files(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")
    (tmp_path / "aardvark.md").touch()
    d = tmp_path / "zebra"
    d.mkdir()
    (d / "SKILL.md").touch()
    items = peek(tmp_path, tmp_path)
    assert items[0]["type"] == "skill"
    assert items[1]["name"] == "aardvark.md"


def test_peek_skips_own_summary(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "SKILLS.md").write_text("---\ndescription: routing\n---\n")
    (skills_dir / "real-skill").mkdir()
    ((skills_dir / "real-skill") / "SKILL.md").touch()
    items = peek(skills_dir, tmp_path)
    names = [i["name"] for i in items]
    assert "SKILLS.md" not in names
    assert "real-skill" in names
