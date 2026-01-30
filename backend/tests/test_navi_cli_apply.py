from pathlib import Path

from backend.cli.navi_cli import main
from backend.services.action_apply import apply_file_edits


def test_apply_file_edits_create_and_modify(tmp_path: Path):
    created, modified, warnings = apply_file_edits(
        str(tmp_path),
        [
            {"filePath": "sample.txt", "content": "hello", "operation": "create"},
        ],
    )
    assert len(created) == 1
    assert len(modified) == 0
    assert not warnings
    assert (tmp_path / "sample.txt").read_text() == "hello"

    created, modified, warnings = apply_file_edits(
        str(tmp_path),
        [
            {"filePath": "sample.txt", "content": "updated", "operation": "modify"},
        ],
    )
    assert len(created) == 0
    assert len(modified) == 1
    assert not warnings
    assert (tmp_path / "sample.txt").read_text() == "updated"


def test_apply_file_edits_rejects_path_escape(tmp_path: Path):
    created, modified, warnings = apply_file_edits(
        str(tmp_path),
        [
            {"filePath": "../outside.txt", "content": "nope", "operation": "create"},
        ],
    )
    assert not created
    assert not modified
    assert warnings
    assert not (tmp_path.parent / "outside.txt").exists()


def test_cli_apply_command(tmp_path: Path):
    response_path = tmp_path / "response.json"
    response_path.write_text(
        """
{
  "file_edits": [
    {"filePath": "cli_output.txt", "content": "from cli", "operation": "create"}
  ],
  "commands_run": []
}
        """.strip()
    )

    exit_code = main(
        [
            "apply",
            "--response",
            str(response_path),
            "--workspace",
            str(tmp_path),
            "--no-commands",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "cli_output.txt").read_text() == "from cli"
