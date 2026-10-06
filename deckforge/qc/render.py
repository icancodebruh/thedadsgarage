"""Renders a .pptx to one PNG per slide via headless LibreOffice + pdftoppm."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class RenderError(RuntimeError):
    """LibreOffice or Poppler is missing or failed."""


def _tool(env_var: str, default: str) -> str:
    exe = shutil.which(os.environ.get(env_var, default))
    if exe is None:
        raise RenderError(f"'{default}' not found on PATH (override with ${env_var})")
    return exe


def render_slides(pptx: Path, out_dir: Path, dpi: int = 110, timeout_s: int = 180) -> list[Path]:
    soffice = _tool("DECKFORGE_SOFFICE", "soffice")
    pdftoppm = _tool("DECKFORGE_PDFTOPPM", "pdftoppm")
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("slide-*.png"):
        stale.unlink()
    with tempfile.TemporaryDirectory(prefix="deckforge_") as tmp:
        tmp_path = Path(tmp)
        # An isolated profile avoids clashing with a running LibreOffice instance.
        profile = (tmp_path / "profile").as_uri()
        env = {**os.environ, "SAL_USE_VCLPLUGIN": "svp"}
        cmd = [
            soffice,
            f"-env:UserInstallation={profile}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmp_path),
            str(pptx),
        ]
        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True, timeout=timeout_s)
            pdf = tmp_path / f"{pptx.stem}.pdf"
            if not pdf.exists():
                raise RenderError(f"LibreOffice produced no PDF for {pptx.name}")
            subprocess.run(
                [pdftoppm, "-png", "-r", str(dpi), str(pdf), str(out_dir / "slide")],
                check=True,
                capture_output=True,
                timeout=timeout_s,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise RenderError(f"rendering {pptx.name} failed: {exc}") from exc
    return sorted(out_dir.glob("slide-*.png"))
