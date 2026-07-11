from __future__ import annotations

from pathlib import Path
from typing import Literal, NewType

FileId = NewType("FileId", str)
ModuleId = NewType("ModuleId", str)
ImportSpecifier = NewType("ImportSpecifier", str)


class DuplicateIdentityError(ValueError):
    code = "duplicate_identity"

    def __init__(
        self,
        identity_kind: Literal["file", "module"],
        identity: str,
        existing_file_id: FileId,
        duplicate_file_id: FileId,
    ) -> None:
        self.identity_kind = identity_kind
        self.identity = identity
        self.existing_file_id = existing_file_id
        self.duplicate_file_id = duplicate_file_id
        super().__init__(
            f"Duplicate {identity_kind} identity {identity!r}: "
            f"{existing_file_id!r} and {duplicate_file_id!r}"
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "identity_kind": self.identity_kind,
            "identity": self.identity,
            "existing_file_id": self.existing_file_id,
            "duplicate_file_id": self.duplicate_file_id,
        }


def file_id_for_path(root: Path, path: Path) -> FileId:
    return FileId(path.relative_to(root).as_posix().strip("/"))


def module_id_for_path(root: Path, path: Path) -> ModuleId:
    relative_path = path.relative_to(root)
    return ModuleId(relative_path.with_suffix("").as_posix().strip("/"))
