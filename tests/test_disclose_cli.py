import json
import pytest
from pathlib import Path
from unittest.mock import patch
import scripts.disclose as disclose


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    sd = tmp_path / "sessions"
    sd.mkdir()
    monkeypatch.setattr(disclose, "SESSIONS_DIR", sd)
    return sd


@pytest.fixture
def simple_harness(tmp_path):
    """A minimal harness: one skill, one reference file."""
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")

    skills = tmp_path / "skills"
    skills.mkdir()
    skill = skills / "my-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\ndescription: Does something useful\n---\n")

    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "guide.md").write_text("---\ndescription: Usage guide\n---\n")

    return tmp_path


@pytest.fixture
def nested_harness(tmp_path):
    """A harness with a group containing two skills."""
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")

    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "SKILLS.md").write_text("---\ndescription: All skills\n---\nRouting info here.")

    group = skills / "database"
    group.mkdir()
    (group / "DATABASE.md").write_text("---\ndescription: DB skills\n---\nDatabase routing.")

    for name in ("query", "migrate"):
        s = group / name
        s.mkdir()
        (s / "SKILL.md").write_text(f"---\ndescription: {name.title()} skill\n---\n")

    return tmp_path


def test_cmd_start_returns_exploring(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "exploring"
    assert "session" in out
    assert out["location"] == "."
    assert len(out["items"]) == 2


def test_cmd_start_creates_session_file(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    out = json.loads(capsys.readouterr().out)
    sid = out["session"]
    assert (sessions_dir / f"harness_{sid}.json").exists()


def test_cmd_start_invalid_path(sessions_dir, capsys):
    with pytest.raises(SystemExit):
        disclose.cmd_start("/nonexistent/path", "bfs")
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_cmd_select_skill_goes_to_resources(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    # Find the skills group item id
    skills_item = next(i for i in start_out["items"] if i["name"] == "skills")

    disclose.cmd_select(sid, str(skills_item["id"]))
    select_out = json.loads(capsys.readouterr().out)

    # Now peeking inside skills/ — select my-skill
    assert select_out["status"] == "exploring"
    skill_item = next(i for i in select_out["items"] if i["name"] == "my-skill")

    disclose.cmd_select(sid, str(skill_item["id"]))
    final_out = json.loads(capsys.readouterr().out)

    # references group is still in queue, so not complete yet
    # Select nothing to exhaust
    if final_out["status"] == "exploring":
        disclose.cmd_select(sid, "")
        final_out = json.loads(capsys.readouterr().out)

    assert final_out["status"] == "complete"
    resource_names = [r["name"] for r in final_out["resources"]]
    assert "my-skill" in resource_names


def test_cmd_select_empty_exhausts_queue(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    disclose.cmd_select(sid, "")
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "complete"
    assert out["resources"] == []


def test_cmd_select_session_deleted_on_complete(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    disclose.cmd_select(sid, "")
    capsys.readouterr()

    assert not (sessions_dir / f"harness_{sid}.json").exists()


def test_bfs_explores_breadth_first(nested_harness, sessions_dir, capsys):
    """In BFS, after selecting a group, other same-level items are explored first."""
    refs = nested_harness / "references"
    refs.mkdir()

    disclose.cmd_start(str(nested_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    # Select both top-level groups (skills and references)
    all_ids = ",".join(str(i["id"]) for i in start_out["items"])
    disclose.cmd_select(sid, all_ids)
    out = json.loads(capsys.readouterr().out)

    # BFS: should be exploring skills/ next (first selected)
    assert out["location"] == "skills"


def test_dfs_explores_depth_first(nested_harness, sessions_dir, capsys):
    """In DFS, after selecting a group inside skills, we dive into it before references."""
    refs = nested_harness / "references"
    refs.mkdir()

    disclose.cmd_start(str(nested_harness), "dfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    # Select both top-level groups
    all_ids = ",".join(str(i["id"]) for i in start_out["items"])
    disclose.cmd_select(sid, all_ids)
    out1 = json.loads(capsys.readouterr().out)
    assert out1["location"] == "skills"

    # Select the database group inside skills
    db_item = next(i for i in out1["items"] if i["name"] == "database")
    disclose.cmd_select(sid, str(db_item["id"]))
    out2 = json.loads(capsys.readouterr().out)

    # DFS: should dive into database/ before exploring references/
    assert out2["location"] == "skills/database"


def test_cmd_cancel_deletes_session(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]
    capsys.readouterr()

    disclose.cmd_cancel(sid)
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "cancelled"
    assert not (sessions_dir / f"harness_{sid}.json").exists()


def test_context_included_when_summary_exists(nested_harness, sessions_dir, capsys):
    disclose.cmd_start(str(nested_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    skills_item = next(i for i in start_out["items"] if i["name"] == "skills")
    disclose.cmd_select(sid, str(skills_item["id"]))
    out = json.loads(capsys.readouterr().out)

    # skills/ has SKILLS.md with body "Routing info here." — should appear as context
    assert "context" in out
    assert "Routing info here." in out["context"]


def test_resource_type_matches_top_level_folder(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    refs_item = next(i for i in start_out["items"] if i["name"] == "references")
    disclose.cmd_select(sid, str(refs_item["id"]))
    out = json.loads(capsys.readouterr().out)

    guide_item = next(i for i in out["items"] if i["name"] == "guide.md")
    disclose.cmd_select(sid, str(guide_item["id"]))
    final = json.loads(capsys.readouterr().out)

    if final["status"] == "exploring":
        disclose.cmd_select(sid, "")
        final = json.loads(capsys.readouterr().out)

    ref_resource = next(r for r in final["resources"] if r["name"] == "guide.md")
    assert ref_resource["type"] == "references"


# ── Session stamping ────────────────────────────────────────────────────────

def test_complete_resources_stamped_with_session(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    refs_item = next(i for i in start_out["items"] if i["name"] == "references")
    disclose.cmd_select(sid, str(refs_item["id"]))
    out = json.loads(capsys.readouterr().out)

    guide_item = next(i for i in out["items"] if i["name"] == "guide.md")
    disclose.cmd_select(sid, str(guide_item["id"]))
    final = json.loads(capsys.readouterr().out)

    if final["status"] == "exploring":
        disclose.cmd_select(sid, "")
        final = json.loads(capsys.readouterr().out)

    assert final["status"] == "complete"
    for r in final["resources"]:
        assert r["session"] == sid


# ── Hybrid mode ─────────────────────────────────────────────────────────────

@pytest.fixture
def wide_harness(tmp_path):
    """Two top-level skill groups plus a reference file — good for parallel branching."""
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")

    for name in ("auth", "payments"):
        d = tmp_path / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\ndescription: {name.title()} skill\n---\n")

    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "guide.md").write_text("---\ndescription: Usage guide\n---\n")

    return tmp_path


def test_hybrid_emits_parallelize(wide_harness, sessions_dir, capsys):
    disclose.cmd_start(str(wide_harness), "hybrid", max_parallel=1)
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    all_ids = ",".join(str(i["id"]) for i in start_out["items"])
    disclose.cmd_select(sid, all_ids)
    out = json.loads(capsys.readouterr().out)

    assert out["status"] == "parallelize"
    assert out["session"] == sid
    assert len(out["branches"]) == len(start_out["items"])


def test_hybrid_branch_sessions_are_created(wide_harness, sessions_dir, capsys):
    disclose.cmd_start(str(wide_harness), "hybrid", max_parallel=1)
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    all_ids = ",".join(str(i["id"]) for i in start_out["items"])
    disclose.cmd_select(sid, all_ids)
    out = json.loads(capsys.readouterr().out)

    assert out["status"] == "parallelize"
    for branch in out["branches"]:
        assert (sessions_dir / f"harness_{branch['session']}.json").exists()
        assert "items" in branch


def test_hybrid_parent_session_deleted_after_fork(wide_harness, sessions_dir, capsys):
    disclose.cmd_start(str(wide_harness), "hybrid", max_parallel=1)
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    all_ids = ",".join(str(i["id"]) for i in start_out["items"])
    disclose.cmd_select(sid, all_ids)
    capsys.readouterr()

    assert not (sessions_dir / f"harness_{sid}.json").exists()


def test_hybrid_branch_items_match_session_state(wide_harness, sessions_dir, capsys):
    """Branch descriptor items must match the session's current_items so sub-agents
    can call --select immediately without any extra discovery step."""
    disclose.cmd_start(str(wide_harness), "hybrid", max_parallel=1)
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    all_ids = ",".join(str(i["id"]) for i in start_out["items"])
    disclose.cmd_select(sid, all_ids)
    parallelize_out = json.loads(capsys.readouterr().out)

    for branch in parallelize_out["branches"]:
        branch_state = json.loads(
            (sessions_dir / f"harness_{branch['session']}.json").read_text()
        )
        state_item_ids = {i["id"] for i in branch_state["current_items"]}
        resp_item_ids  = {i["id"] for i in branch["items"]}
        assert resp_item_ids == state_item_ids
        # path must not leak into the response items
        for item in branch["items"]:
            assert "path" not in item


def test_hybrid_branch_can_be_continued(wide_harness, sessions_dir, capsys):
    disclose.cmd_start(str(wide_harness), "hybrid", max_parallel=1)
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    all_ids = ",".join(str(i["id"]) for i in start_out["items"])
    disclose.cmd_select(sid, all_ids)
    parallelize_out = json.loads(capsys.readouterr().out)

    branch = parallelize_out["branches"][0]
    branch_sid = branch["session"]

    # Use items from the branch descriptor directly — no session file read needed
    all_branch_ids = ",".join(str(i["id"]) for i in branch["items"])
    disclose.cmd_select(branch_sid, all_branch_ids)
    final = json.loads(capsys.readouterr().out)

    assert final["status"] in ("complete", "exploring")


def test_hybrid_bfs_phase_resources_in_parallelize(wide_harness, sessions_dir, capsys):
    """Resources found during BFS (before fork) appear in the parallelize response."""
    # Add a direct skill at root level so it's found during BFS
    root_skill = wide_harness / "root-skill"
    root_skill.mkdir()
    (root_skill / "SKILL.md").write_text("---\ndescription: Root-level skill\n---\n")

    disclose.cmd_start(str(wide_harness), "hybrid", max_parallel=1)
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    # Select the root skill (resource) and the groups (will trigger fork)
    all_ids = ",".join(str(i["id"]) for i in start_out["items"])
    disclose.cmd_select(sid, all_ids)
    out = json.loads(capsys.readouterr().out)

    assert out["status"] == "parallelize"
    assert "resources" in out
    resource_names = [r["name"] for r in out["resources"]]
    assert "root-skill" in resource_names
    for r in out["resources"]:
        assert r["session"] == sid


@pytest.fixture
def funnel_harness(tmp_path):
    """root → top/ (group) → {A/ (group), B/ (group)} → each has one skill inside.

    The harness is narrow at the root (one group) and widens one level down.
    Used to verify that hybrid mode keeps BFS-ing past narrow levels until the
    queue is wide enough to meet the max_parallel threshold.
    """
    (tmp_path / ".leaf-detectors").write_text("skill=SKILL.md\n")

    for name in ("A", "B"):
        skill = tmp_path / "top" / name / f"{name.lower()}-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\ndescription: {name} skill\n---\n")
    return tmp_path


def test_hybrid_forks_when_queue_wide_enough(funnel_harness, sessions_dir, capsys):
    """BFS keeps going past a narrow level and forks once the queue has 2+ groups.

    funnel_harness: root → top/ → {A/, B/} → each has one skill

    Selecting top (queue=1) stays below threshold; advancing into top shows A and B.
    Selecting both (queue=2) meets the threshold and triggers the fork.
    """
    disclose.cmd_start(str(funnel_harness), "hybrid", max_parallel=2)
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    # Queue grows to 1 (top) — below threshold, keep exploring
    top_item = next(i for i in start_out["items"] if i["name"] == "top")
    disclose.cmd_select(sid, str(top_item["id"]))
    out1 = json.loads(capsys.readouterr().out)
    assert out1["status"] == "exploring"
    assert out1["location"] == "top"

    # Select A and B (both groups) — queue grows to 2, meets threshold → fork
    all_ids = ",".join(str(i["id"]) for i in out1["items"])
    disclose.cmd_select(sid, all_ids)
    out2 = json.loads(capsys.readouterr().out)
    assert out2["status"] == "parallelize"
    assert len(out2["branches"]) == 2
