from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class EvidenceLimits:
    max_file_patch_chars: int = 12_000
    max_total_patch_chars: int = 50_000
    generated_path_parts: tuple[str, ...] = (
        ".venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        "dist",
        "build",
    )
    binary_extensions: tuple[str, ...] = (
        ".bmp",
        ".gif",
        ".ico",
        ".jpg",
        ".jpeg",
        ".pdf",
        ".png",
        ".webp",
        ".zip",
    )

    def is_generated_path(self, filename: str) -> bool:
        parts = PurePosixPath(filename).parts
        return any(part in self.generated_path_parts for part in parts)

    def is_binary_path(self, filename: str) -> bool:
        return PurePosixPath(filename).suffix.lower() in self.binary_extensions
