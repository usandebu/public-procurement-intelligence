import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def import_without_pypdf(*modules: str) -> subprocess.CompletedProcess:
    code = "import sys; sys.modules['pypdf'] = None; " + "; ".join(
        f"import {module}" for module in modules
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(SRC), "PATH": ""},
    )


def test_modules_used_by_notebooks_without_pypdf_import_without_it():
    result = import_without_pypdf(
        "procurement.feed",
        "procurement.silver",
        "procurement.documents",
        "procurement.chunking",
        "procurement.pages",
    )

    assert result.returncode == 0, result.stderr


def test_pdf_text_module_does_require_pypdf():
    result = import_without_pypdf("procurement.pdf_text")

    assert result.returncode != 0
