"""Compatibility entrypoint for the isolated audit recovery test."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("audit_recovery.py")), run_name="__main__")
