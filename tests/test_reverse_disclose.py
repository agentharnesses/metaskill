import json
import pytest
from pathlib import Path
from scripts.reverse_disclose import (
    find_root,
    collect_ancestors,
    spec_files_in,
    scan_ancestors,
    cmd_run,
)


# ── find_root ────────────────────────────────────────────────────────────────

def test_find_root_locates_harness_md(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    skill_file = tmp_path / "skills" / "auth" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.touch()
    assert find_root(skill_file) == tmp_path


def test_find_root_directory_target(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    skill_dir = tmp_path / "skills" / "auth"
    skill_dir.mkdir(parents=True)
    assert find_root(skill_dir) == tmp_path


def test_find_root_fallback_when_no_harness_md(tmp_path):
    deep = tmp_path / "a" / "b" / "c.md"
    deep.parent.mkdir(parents=True)
    deep.touch()
    assert find_root(deep) == deep.parent


# ── collect_ancestors ────────────────────────────────────────────────────────

def test_collect_ancestors_order(tmp_path):
    target = tmp_path / "a" / "b" / "c.md"
    target.parent.mkdir(parents=True)
    target.touch()
    ancestors = collect_ancestors(target, tmp_path)
    assert ancestors[0] == tmp_path / "a" / "b"
    assert ancestors[1] == tmp_path / "a"
    assert ancestors[2] == tmp_path


def test_collect_ancestors_includes_root(tmp_path):
    target = tmp_path / "file.md"
    target.touch()
    assert tmp_path in collect_ancestors(target, tmp_path)


def test_collect_ancestors_stops_at_root(tmp_path):
    target = tmp_path / "file.md"
    target.touch()
    assert tmp_path.parent not in collect_ancestors(target, tmp_path)


# ── spec_files_in ─────────────────────────────────────────────────────────────

def test_spec_files_in_finds_harness_md(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    found = spec_files_in(tmp_path, tmp_path)
    assert any(e["kind"] == "harness" for e in found)


def test_spec_files_in_finds_routing_file(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "SKILLS.md").touch()
    found = spec_files_in(skills_dir, tmp_path)
    assert any(e["kind"] == "routing" for e in found)


def test_spec_files_in_finds_skill_md(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").touch()
    found = spec_files_in(skill_dir, tmp_path)
    assert any(e["kind"] == "skill" for e in found)


def test_spec_files_in_excludes_target(tmp_path):
    skill_dir = tmp_path / "auth"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.touch()
    found = spec_files_in(skill_dir, tmp_path, exclude=skill_md)
    assert not any(e["kind"] == "skill" for e in found)


def test_spec_files_in_empty_when_none_present(tmp_path):
    subdir = tmp_path / "empty"
    subdir.mkdir()
    assert spec_files_in(subdir, tmp_path) == []


def test_spec_files_in_finds_config_custom_leaf(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("mcp-server=MCP-SERVER.md\n")
    d = tmp_path / "my-server"
    d.mkdir()
    (d / "MCP-SERVER.md").touch()
    found = spec_files_in(d, tmp_path)
    assert any(e["kind"] == "mcp-server" for e in found)


def test_spec_files_in_finds_harnessleaf_type(tmp_path):
    d = tmp_path / "my-server"
    d.mkdir()
    (d / ".harnessleaf").write_text("mcp-server")
    (d / "MCP-SERVER.md").touch()
    found = spec_files_in(d, tmp_path)
    assert any(e["kind"] == "mcp-server" for e in found)


def test_spec_files_in_multiple_kinds(tmp_path):
    # A directory that has both HARNESS.md and a routing file is unusual but valid
    (tmp_path / "HARNESS.md").touch()
    (tmp_path / (tmp_path.name.upper() + ".md")).touch()
    kinds = {e["kind"] for e in spec_files_in(tmp_path, tmp_path)}
    assert "harness" in kinds
    assert "routing" in kinds


def test_spec_files_in_no_duplicate_when_dir_named_harness(tmp_path):
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir()
    (harness_dir / "HARNESS.md").touch()
    found = spec_files_in(harness_dir, tmp_path)
    assert len(found) == 1
    assert found[0]["kind"] == "harness"


def test_spec_files_in_routing_name_inherited_from_top_level(tmp_path):
    nested = tmp_path / "skills" / "maintenance"
    nested.mkdir(parents=True)
    (nested / "SKILLS.md").touch()
    found = spec_files_in(nested, tmp_path)
    assert any(e["kind"] == "routing" and e["path"].endswith("SKILLS.md") for e in found)


def test_spec_files_in_routing_name_resets_at_nested_harness_md(tmp_path):
    plugin = tmp_path / "skills" / "plugin-x"
    plugin.mkdir(parents=True)
    (plugin / "HARNESS.md").touch()
    nested = plugin / "tools"
    nested.mkdir()
    (nested / "TOOLS.md").touch()
    found = spec_files_in(nested, tmp_path)
    assert any(e["kind"] == "routing" and e["path"].endswith("TOOLS.md") for e in found)
    assert not any(e["path"].endswith("SKILLS.md") for e in found)


# ── scan_ancestors ───────────────────────────────────────────────────────────

def test_scan_ancestors_finds_harness_at_root(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    target = tmp_path / "skills" / "auth" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.touch()

    refs = scan_ancestors(target, tmp_path)
    assert any(r["kind"] == "harness" for r in refs)


def test_scan_ancestors_finds_routing_in_parent(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "SKILLS.md").touch()
    skill_dir = skills_dir / "auth"
    skill_dir.mkdir()
    target = skill_dir / "SKILL.md"
    target.touch()

    refs = scan_ancestors(target, tmp_path)
    assert any(r["kind"] == "routing" for r in refs)


def test_scan_ancestors_finds_skill_md_in_parent(tmp_path):
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")
    skill_dir = tmp_path / "auth"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").touch()
    target = skill_dir / "guide.md"
    target.touch()

    refs = scan_ancestors(target, tmp_path)
    assert any(r["kind"] == "skill" for r in refs)


def test_scan_ancestors_excludes_target_itself(tmp_path):
    skill_dir = tmp_path / "auth"
    skill_dir.mkdir()
    target = skill_dir / "SKILL.md"
    target.touch()

    refs = scan_ancestors(target, tmp_path)
    assert all(r["path"] != str(target) for r in refs)


def test_scan_ancestors_resets_at_nested_harness_md(tmp_path):
    # tools_dir sits directly below plugin's own HARNESS.md, so a further-nested
    # subgroup below it must still resolve to TOOLS.md — inherited from tools_dir,
    # not from skills_dir above the HARNESS.md boundary (which would give SKILLS.md
    # under the pre-fix, no-reset behavior).
    (tmp_path / "HARNESS.md").touch()
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "SKILLS.md").touch()

    plugin = skills_dir / "plugin-x"
    plugin.mkdir()
    (plugin / "HARNESS.md").touch()

    tools_dir = plugin / "tools"
    tools_dir.mkdir()
    (tools_dir / "TOOLS.md").touch()

    subgroup = tools_dir / "database"
    subgroup.mkdir()
    (subgroup / "TOOLS.md").touch()

    target = subgroup / "query-db" / "SKILL.md"
    target.parent.mkdir()
    target.touch()

    refs = scan_ancestors(target, tmp_path)
    routing_paths = {r["path"] for r in refs if r["kind"] == "routing"}
    assert str(subgroup / "TOOLS.md") in routing_paths
    assert str(tools_dir / "TOOLS.md") in routing_paths
    # skills_dir's own SKILLS.md is still a legitimate ancestor reference (it's
    # above the HARNESS.md boundary) — but nothing along this chain should ever
    # be misnamed SKILLS.md *inside* the nested-harness subtree.
    assert not any(p.endswith("/database/SKILLS.md") for p in routing_paths)


def test_scan_ancestors_nearest_first(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "SKILLS.md").touch()
    target = skills_dir / "auth" / "SKILL.md"
    target.parent.mkdir()
    target.touch()

    refs = scan_ancestors(target, tmp_path)
    paths = [r["path"] for r in refs]
    # SKILLS.md (parent) should appear before HARNESS.md (root)
    assert paths.index(str(skills_dir / "SKILLS.md")) < paths.index(str(tmp_path / "HARNESS.md"))


# ── cmd_run ───────────────────────────────────────────────────────────────────

def test_cmd_run_output_shape(tmp_path, capsys):
    (tmp_path / "HARNESS.md").touch()
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "SKILLS.md").touch()
    target = skills_dir / "auth" / "SKILL.md"
    target.parent.mkdir()
    target.touch()

    cmd_run(str(target), str(tmp_path))
    out = json.loads(capsys.readouterr().out)

    assert out["status"] == "complete"
    assert out["target"] == "skills/auth/SKILL.md"
    assert out["root"] == str(tmp_path)
    assert "self" in out
    kinds = {r["kind"] for r in out["references"]}
    assert "harness" in kinds
    assert "routing" in kinds


def test_cmd_run_no_self_for_non_md(tmp_path, capsys):
    target = tmp_path / "data.json"
    target.write_text("{}")
    cmd_run(str(target), str(tmp_path))
    out = json.loads(capsys.readouterr().out)
    assert "self" not in out


def test_cmd_run_nonexistent_target(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cmd_run(str(tmp_path / "nonexistent.md"), None)
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_cmd_run_explicit_root(tmp_path, capsys):
    (tmp_path / "HARNESS.md").touch()
    target = tmp_path / "skills" / "thing.md"
    target.parent.mkdir()
    target.touch()

    cmd_run(str(target), str(tmp_path))
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "complete"
    assert any(r["kind"] == "harness" for r in out["references"])


def test_cmd_run_autodetects_root_from_harness_md(tmp_path, capsys):
    (tmp_path / "HARNESS.md").touch()
    target = tmp_path / "skills" / "thing.md"
    target.parent.mkdir()
    target.touch()

    cmd_run(str(target), None)
    out = json.loads(capsys.readouterr().out)
    assert out["root"] == str(tmp_path)
