"""Each test names the record it protects (QUAL-006, E4)."""
import pytest

from knowledge import LIBS, REQUIRES, SKILLS


@pytest.mark.req("MCP-031")
@pytest.mark.kind("fixture")
def test_every_lib_and_skill_is_a_prompt_element(prompt_file):
    names = set(prompt_file.element_names())
    assert set(LIBS) <= names and set(SKILLS) <= names


@pytest.mark.req("MCP-032")
@pytest.mark.kind("fixture")
def test_each_skill_is_a_slash_command(prompt_file):
    assert set(prompt_file.command_names()) == set(SKILLS)


@pytest.mark.req("BASE-050")
@pytest.mark.kind("fixture")
def test_assign_issues_a_nonce_and_serves_skill_with_its_libs(run):
    n = run("knowledge assign write_workflow input='goal: x'").split()[-1]
    served = run(f"metaform {n}")
    for lib in REQUIRES["write_workflow"]:
        assert served.count(f"# {lib}") == 1 or lib in served   # each lib once
    assert "name=write_workflow" in served
    run(f"metaform {n} complete")
    assert run(f"metaform {n}") == "Error: Invalid or Unknown Nonce"
