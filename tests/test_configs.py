"""Smoke tests for the shipped example config."""

from pathlib import Path

import pytest

from server import load_fixtures, load_schema

CONFIGS = Path(__file__).resolve().parent.parent / "configs"

SHIPPED = [
    pytest.param(
        CONFIGS / "example",
        ("fixtures-basic-flow.json",),
        id="example",
    ),
]


SPEC_TOOL_FIELDS = ("name", "description", "inputSchema", "outputSchema", "outputExample")


@pytest.mark.parametrize("config_dir, fixture_files", SHIPPED)
def test_shipped_schema_meets_spec(config_dir: Path, fixture_files: tuple[str, ...]):
    """Every shipped tool has the SCHEMA.md-required fields."""
    assert fixture_files
    schema = load_schema(config_dir / "schema.json")
    assert schema.get("name"), f"{config_dir.name}: missing top-level name"
    assert schema.get("tools"), f"{config_dir.name}: tools must be a non-empty list"
    for index, tool in enumerate(schema["tools"]):
        for field in SPEC_TOOL_FIELDS:
            assert tool.get(field), (
                f"{config_dir.name} tools[{index}] ({tool.get('name')!r}) missing {field}"
            )


@pytest.mark.parametrize("config_dir, fixture_files", SHIPPED)
def test_shipped_fixtures_match_schema(config_dir: Path, fixture_files: tuple[str, ...]):
    schema = load_schema(config_dir / "schema.json")
    tools = {tool["name"]: tool for tool in schema["tools"]}

    for fixtures_name in fixture_files:
        fixtures = load_fixtures(config_dir / fixtures_name)
        for step in fixtures["sequence"]:
            tool_name = step["tool"]
            assert tool_name in tools, f"{fixtures_name}: unknown tool {tool_name}"
            input_props = tools[tool_name].get("inputSchema", {}).get("properties") or {}
            for key in step.get("input") or {}:
                assert key in input_props, (
                    f"{fixtures_name}: {tool_name} input {key!r} not in schema"
                )
