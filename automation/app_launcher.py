"""
automation/app_launcher.py — Open, close, and switch between applications
"""
import os
import subprocess
import webbrowser
import psutil
from utils.logger import logger
from utils.config import get_section


class AppLauncher:
    """Launch and manage desktop applications."""

    def __init__(self):
        raw_map = get_section("apps") or {}
        # Expand env vars ONCE at startup (cached)
        self._app_map = {k: os.path.expandvars(v) for k, v in raw_map.items()}

        self._builtin = {
            "notepad":       "notepad.exe",
            "calculator":    "calc.exe",
            "paint":         "mspaint.exe",
            "explorer":      "explorer.exe",
            "task manager":  "taskmgr.exe",
            "control panel": "control.exe",
            "settings":      "ms-settings:",
            "terminal":      "wt.exe",
            "cmd":           "cmd.exe",
            "powershell":    "powershell.exe",
        }

        logger.info(f"AppLauncher ready. {len(self._app_map)} apps in config.")

    def open(self, app_name: str) -> bool:
        name = app_name.lower().strip()
        logger.info(f"Opening app: '{name}'")

        if name in self._app_map:
            return self._smart_launch(name, self._app_map[name])

        if name in self._builtin:
            return self._smart_launch(name, self._builtin[name])

        for key, path in self._app_map.items():
            if name in key or key in name:
                return self._smart_launch(key, path)

        return self._launch(name)

    def open_url(self, url: str) -> bool:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        logger.info(f"Opening URL: {url}")
        webbrowser.open(url)
        return True

    def close(self, app_name: str) -> bool:
        name = app_name.lower()
        killed = 0
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if name in proc.info["name"].lower():
                    proc.terminate()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed:
            logger.info(f"Closed {killed} instance(s) of '{app_name}'.")
        else:
            logger.warning(f"No running process found for '{app_name}'.")
        return killed > 0

    def is_running(self, app_name: str) -> bool:
        name = app_name.lower()
        for proc in psutil.process_iter(["name"]):
            try:
                if name in proc.info["name"].lower():
                    return True
            except psutil.NoSuchProcess:
                pass
        return False

    def list_running(self) -> list[str]:
        names = set()
        for proc in psutil.process_iter(["name"]):
            try:
                n = proc.info["name"]
                if n:
                    names.add(n)
            except psutil.NoSuchProcess:
                pass
        return sorted(names)

    def _smart_launch(self, app_key: str, path: str) -> bool:
        """Launch only if not already running."""
        proc_name = os.path.basename(path).lower()
        if self.is_running(proc_name):
            logger.info(f"'{app_key}' is already running — skipping launch.")
            return True
        return self._launch(path)

    def _launch(self, path: str) -> bool:
        try:
            if path.startswith("ms-") or path.startswith("shell:"):
                # Microsoft Store apps and shell: URIs
                subprocess.Popen(["explorer.exe", path])
            elif os.name == "nt" and os.path.isfile(path):
                # Fastest Windows launch for regular exe files
                os.startfile(path)
            else:
                subprocess.Popen(
                    path,
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
                )
            logger.info(f"Launched: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to launch '{path}': {e}")
            return False