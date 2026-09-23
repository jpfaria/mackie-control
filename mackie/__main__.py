"""`python -m mackie`: what the LaunchAgent runs (see `service.py`)."""
import sys

from .cli import main

sys.exit(main())
