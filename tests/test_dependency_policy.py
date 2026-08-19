import tomllib
from pathlib import Path


def test_security_dependency_floor_documents_starlette_multipart_dos_fix():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text())
    dependencies = pyproject["project"]["dependencies"]

    assert "fastapi>=0.115.3,<1.0" in dependencies
    assert "starlette>=0.40.0,<2.0" in dependencies
