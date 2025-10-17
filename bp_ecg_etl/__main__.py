"""Entry point for running bp_ecg_etl as a module."""
import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
