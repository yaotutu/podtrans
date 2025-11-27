"""Entry point for running podtrans as a module.

This allows running: python -m podtrans
"""

from podtrans.cli import app

if __name__ == "__main__":
    app()
