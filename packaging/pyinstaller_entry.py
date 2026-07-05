"""PyInstaller entry point for the GUI app."""

from src.main import main


if __name__ == "__main__":
    raise SystemExit(main(["gui"]))
