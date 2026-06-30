from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modwire_extraction import ModwireExtraction


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).with_name("projects.json")


@dataclass(frozen=True)
class Project:
    language: str
    project_id: str
    owner: str
    repo: str
    branch: str | None

    @property
    def label(self) -> str:
        return f"{self.language}/{self.project_id}"

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh large GitHub projects and time modwire extraction."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to the big-project JSON config.",
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Use existing clones without fetching updates.",
    )
    parser.add_argument(
        "--only",
        metavar="LANGUAGE/PROJECT",
        action="append",
        default=[],
        help="Run only one project label. Can be passed multiple times.",
    )
    args = parser.parse_args()

    config = _load_config(args.config)
    clone_root = REPO_ROOT / config["github"]["clone_root"]
    selected = set(args.only)
    projects = [
        project
        for project in _iter_projects(config)
        if not selected or project.label in selected
    ]

    if selected:
        labels = {project.label for project in projects}
        missing = sorted(selected - labels)
        if missing:
            print(f"Unknown project label(s): {', '.join(missing)}", file=sys.stderr)
            return 2

    clone_root.mkdir(parents=True, exist_ok=True)
    print(f"Big project root: {clone_root.relative_to(REPO_ROOT)}")
    print(f"Projects: {len(projects)}")

    failures = 0
    for project in projects:
        project_root = clone_root / project.language / project.project_id
        started = time.perf_counter()
        print(f"\n{project.label} ({project.full_name})")

        try:
            sync_seconds = 0.0
            if not args.no_refresh or not project_root.exists():
                sync_seconds = _timed(
                    lambda: _refresh_project(config, project, project_root)
                )
            elif not (project_root / ".git").is_dir():
                raise RuntimeError(f"Existing path is not a git clone: {project_root}")

            extract_started = time.perf_counter()
            code_map = ModwireExtraction(project_root).generate_map(project.language)
            extract_seconds = time.perf_counter() - extract_started
            total_seconds = time.perf_counter() - started

            print(
                "  "
                f"sync={sync_seconds:.2f}s "
                f"extract={extract_seconds:.2f}s "
                f"total={total_seconds:.2f}s "
                f"files={code_map.extraction.files_found} "
                f"excluded={code_map.extraction.files_excluded}"
            )
        except Exception as error:
            failures += 1
            total_seconds = time.perf_counter() - started
            print(f"  failed after {total_seconds:.2f}s: {error}", file=sys.stderr)

    return 1 if failures else 0


def _load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as config_file:
        config = json.load(config_file)

    if not isinstance(config, dict):
        raise ValueError("Big-project config must be a JSON object.")
    return config


def _iter_projects(config: dict[str, Any]) -> list[Project]:
    projects_config = config.get("projects")
    if not isinstance(projects_config, dict):
        raise ValueError("Big-project config must contain a projects object.")

    projects: list[Project] = []
    for language, entries in projects_config.items():
        if not isinstance(language, str) or not isinstance(entries, list):
            raise ValueError("Project mapping must be language names to arrays.")

        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"Invalid project entry for {language}.")
            projects.append(
                Project(
                    language=language,
                    project_id=_required_str(entry, "id"),
                    owner=_required_str(entry, "owner"),
                    repo=_required_str(entry, "repo"),
                    branch=_optional_str(entry, "branch"),
                )
            )

    return projects


def _refresh_project(
    config: dict[str, Any],
    project: Project,
    project_root: Path,
) -> None:
    if project_root.exists():
        if not (project_root / ".git").is_dir():
            raise RuntimeError(f"Existing path is not a git clone: {project_root}")
        _fetch_project(config, project, project_root)
        return

    project_root.parent.mkdir(parents=True, exist_ok=True)
    _clone_project(config, project, project_root)


def _clone_project(
    config: dict[str, Any],
    project: Project,
    project_root: Path,
) -> None:
    clone_config = config["github"]["clone"]
    command = ["git", "clone"]
    if clone_config.get("depth"):
        command.extend(["--depth", str(clone_config["depth"])])
    if clone_config.get("single_branch"):
        command.append("--single-branch")
    if clone_config.get("tags") is False:
        command.append("--no-tags")
    if project.branch:
        command.extend(["--branch", project.branch])
    command.extend([_clone_url(config, project), str(project_root)])
    _run(command, cwd=REPO_ROOT)


def _fetch_project(
    config: dict[str, Any],
    project: Project,
    project_root: Path,
) -> None:
    clone_config = config["github"]["clone"]
    _run(
        ["git", "remote", "set-url", "origin", _clone_url(config, project)],
        cwd=project_root,
    )

    fetch_command = ["git", "fetch", "--prune"]
    if clone_config.get("depth"):
        fetch_command.append(f"--depth={clone_config['depth']}")
    if clone_config.get("tags") is False:
        fetch_command.append("--no-tags")
    fetch_command.append("origin")
    if project.branch:
        fetch_command.append(project.branch)
    _run(fetch_command, cwd=project_root)

    branch = project.branch or _remote_default_branch(project_root)
    _run(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=project_root)
    _run(["git", "reset", "--hard", f"origin/{branch}"], cwd=project_root)


def _remote_default_branch(project_root: Path) -> str:
    _run(["git", "remote", "set-head", "origin", "--auto"], cwd=project_root)
    ref = _run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        cwd=project_root,
        capture=True,
    )
    prefix = "origin/"
    if not ref.startswith(prefix):
        raise RuntimeError(f"Unexpected origin HEAD ref: {ref}")
    return ref[len(prefix) :]


def _clone_url(config: dict[str, Any], project: Project) -> str:
    github = config["github"]
    return f"{github['scheme']}://{github['host']}/{project.full_name}.git"


def _required_str(entry: dict[str, Any], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Project entry requires a non-empty {key!r} string.")
    return value


def _optional_str(entry: dict[str, Any], key: str) -> str | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"Project entry {key!r} must be a non-empty string.")
    return value


def _timed(operation: Callable[[], None]) -> float:
    started = time.perf_counter()
    operation()
    return time.perf_counter() - started


def _run(command: list[str], cwd: Path, capture: bool = False) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {message}")
    if capture:
        return result.stdout.strip()
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
