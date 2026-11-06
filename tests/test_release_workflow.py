"""Exercise release status handling without bumping or publishing anything."""

from __future__ import annotations

import os
import subprocess

from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize(
    ("setup_status", "bump_status", "increment"),
    [
        (0, 0, "AUTO"),
        (0, 0, "PATCH"),
        (0, 3, "AUTO"),
        (0, 21, "AUTO"),
        (0, 19, "AUTO"),
        (0, 16, "AUTO"),
        (21, 0, "AUTO"),
    ],
)
def test_release_version_statuses(
    tmp_path: Path, setup_status: int, bump_status: int, increment: str
) -> None:
    workflow = Path(__file__).parents[1] / ".github/workflows/prepare-release.yaml"
    steps = yaml.safe_load(workflow.read_text())["jobs"]["prepare"]["steps"]
    setup = next(step["run"] for step in steps if step.get("name") == "Install the release tooling")
    compute = next(step["run"] for step in steps if step.get("id") == "version")
    bin_dir = tmp_path / ".venv/bin"
    bin_dir.mkdir(parents=True)
    uv = bin_dir / "uv"
    uv.write_text('#!/bin/sh\nexit "$SETUP_STATUS"\n')
    uv.chmod(0o755)
    cz = bin_dir / "cz"
    cz.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$ARGS_FILE"\n'
        'if [ "$BUMP_STATUS" = 0 ]; then printf "1.2.3\\n"; '
        'else printf "bump diagnostic\\n" >&2; fi\nexit "$BUMP_STATUS"\n'
    )
    cz.chmod(0o755)
    output = tmp_path / "outputs"
    args = tmp_path / "args"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(output),
        "ARGS_FILE": str(args),
        "SETUP_STATUS": str(setup_status),
        "BUMP_STATUS": str(bump_status),
        "INCREMENT": increment,
    }
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", setup + "\n" + compute],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if setup_status:
        assert result.returncode == setup_status
        assert not args.exists()
        assert not output.exists()
        return
    expected_args = ["bump", "--get-next", "--yes"]
    if increment != "AUTO":
        expected_args += ["--increment", increment]
    assert args.read_text().splitlines() == expected_args
    if bump_status in (0, 3, 21):
        assert result.returncode == 0
        expected = "changed=false\n" if bump_status else "changed=true\nversion=1.2.3\ntag=1.2.3\n"
        assert output.read_text() == expected
    else:
        assert result.returncode == bump_status
        assert not output.exists()
    if bump_status:
        assert "bump diagnostic" in result.stderr
