"""CORE IDE operations — open files in VS Code."""
from __future__ import annotations


def open_in_vscode(folder_path: str, file_path: str) -> dict:
    import os
    import shutil
    import subprocess

    import sys
    if sys.platform == "win32":
        FALLBACKS = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd"),
            os.path.expandvars(r"%PROGRAMFILES%\Microsoft VS Code\bin\code.cmd"),
        ]
    else:
        FALLBACKS = [
            "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",  # macOS
            "/usr/share/code/bin/code",  # Linux snap/deb
        ]
    fallback = next((p for p in FALLBACKS if os.path.exists(p)), None)
    code_bin = shutil.which("code") or fallback
    if not code_bin:
        return {"error": "'code' CLI not found — install it via VS Code: Shell Command: Install 'code' command in PATH"}
    subprocess.Popen([code_bin, "--reuse-window", folder_path, file_path])
    return {"ok": True}
