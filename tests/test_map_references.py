import pytest
import re
from pathlib import Path
from scripts.map_references import get_spec_description, build_tree, format_lines, cmd_run


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


def strip_ansi(s: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*m', '', s)


def _make_spec(kind: str, filename: str, description: str = "") -> dict:
    spec: dict = {"kind": kind, "path": f"/fake/{filename}", "name": filename}
    if description:
        spec["description"] = description
    return spec


def _make_node(name: str, specs=None, children=None) -> dict:
    return {
        "name": name,
        "path": Path(f"/fake/{name}"),
        "specs": specs or [],
        "children": children or [],
    }


def test_format_lines_root_header():
    node = _make_node("my-harness")
    lines = format_lines(node)
    assert lines[0] == "my-harness/"


def test_format_lines_spec_badge_and_name():
    node = _make_node("root", specs=[_make_spec("harness", "HARNESS.md", "My harness")])
    raw = strip_ansi("\n".join(format_lines(node)))
    assert "[harness]" in raw
    assert "HARNESS.md" in raw
    assert "My harness" in raw


def test_format_lines_badge_colors_present():
    node = _make_node("root", specs=[
        _make_spec("harness", "HARNESS.md"),
        _make_spec("routing", "SKILLS.md"),
        _make_spec("skill",   "SKILL.md"),
    ])
    output = "\n".join(format_lines(node))
    assert "\033[1;31m" in output  # harness: bold red
    assert "\033[33m"   in output  # routing: yellow
    assert "\033[36m"   in output  # skill: cyan


def test_format_lines_last_item_uses_corner():
    child = _make_node("skills", specs=[_make_spec("routing", "SKILLS.md")])
    node = _make_node("root", children=[child])
    raw = strip_ansi("\n".join(format_lines(node)))
    assert "└── skills/" in raw


def test_format_lines_non_last_item_uses_tee():
    child_a = _make_node("skills", specs=[_make_spec("routing", "SKILLS.md")])
    child_b = _make_node("refs",   specs=[_make_spec("routing", "REFS.md")])
    node = _make_node("root", children=[child_a, child_b])
    raw = strip_ansi("\n".join(format_lines(node)))
    assert "├── skills/" in raw
    assert "└── refs/" in raw


def test_format_lines_truncates_long_description():
    long_desc = "x" * 80
    node = _make_node("root", specs=[_make_spec("harness", "HARNESS.md", long_desc)])
    raw = strip_ansi("\n".join(format_lines(node)))
    assert long_desc not in raw
    assert "..." in raw


def test_format_lines_no_description_when_absent():
    node = _make_node("root", specs=[_make_spec("harness", "HARNESS.md")])
    raw = strip_ansi("\n".join(format_lines(node)))
    # Line should end after filename with no trailing spaces
    spec_line = [l for l in raw.splitlines() if "HARNESS.md" in l][0]
    assert not spec_line.endswith("  ")


def test_format_lines_nested_indentation():
    auth = _make_node("auth", specs=[_make_spec("skill", "SKILL.md", "Auth")])
    skills = _make_node("skills", children=[auth])
    node = _make_node("root", children=[skills])
    raw = strip_ansi("\n".join(format_lines(node)))
    # auth/ is nested under skills/, so it gets deeper indentation
    auth_line = [l for l in raw.splitlines() if "auth/" in l][0]
    assert auth_line.startswith("    ")  # indented under root's child_prefix


def test_format_lines_root_separator_between_items():
    spec = _make_spec("harness", "HARNESS.md")
    child = _make_node("skills", specs=[_make_spec("routing", "SKILLS.md")])
    node = _make_node("root", specs=[spec], children=[child])
    lines = format_lines(node)
    # A bare "│" separator should appear between spec and child at root level
    assert "│" in lines


def test_cmd_run_prints_tree_for_valid_harness(tmp_path, capsys):
    (tmp_path / "HARNESS.md").write_text("---\ndescription: Test harness\n---\n")
    cmd_run(str(tmp_path))
    out = capsys.readouterr().out
    assert tmp_path.name + "/" in out
    assert "HARNESS.md" in strip_ansi(out)
    assert "[harness]" in strip_ansi(out)


def test_cmd_run_shows_nested_skills(tmp_path, capsys):
    (tmp_path / "HARNESS.md").touch()
    skills = tmp_path / "skills"
    skills.mkdir()
    auth = skills / "auth"
    auth.mkdir()
    (auth / "SKILL.md").write_text("---\ndescription: Auth\n---\n")

    cmd_run(str(tmp_path))
    out = strip_ansi(capsys.readouterr().out)
    assert "skills/" in out
    assert "auth/" in out
    assert "SKILL.md" in out


def test_cmd_run_exits_on_nonexistent_path(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cmd_run(str(tmp_path / "nonexistent"))
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "error" in out.lower()


def test_cmd_run_exits_when_no_spec_files_found(tmp_path, capsys):
    empty = tmp_path / "empty_harness"
    empty.mkdir()
    with pytest.raises(SystemExit):
        cmd_run(str(empty))
    out = capsys.readouterr().out
    assert "no spec files" in out.lower() or "error" in out.lower()
