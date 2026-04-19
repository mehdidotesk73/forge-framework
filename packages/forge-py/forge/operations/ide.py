"""CORE IDE operations — open files in VS Code."""
from __future__ import annotations


def open_in_vscode(folder_path: str, file_path: str) -> dict:
    import os
    import shutil
    import subprocess

    FALLBACK = "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
    code_bin = shutil.which("code") or (FALLBACK if os.path.exists(FALLBACK) else None)
    if not code_bin:
        return {"error": "'code' CLI not found — install it via VS Code: Shell Command: Install 'code' command in PATH"}
    subprocess.Popen([code_bin, "--reuse-window", folder_path, file_path])
    return {"ok": True}
