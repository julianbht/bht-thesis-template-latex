# Simple Makefile to export SVGs from figures.drawio, commit, and push.

PY      := $(if $(wildcard venv/bin/python),venv/bin/python,python3)
SCRIPT  := ./export-drawio-svg.py
DRAWIO  := figures.drawio
MSG     := Updated SVGs

# Main command: export SVGs, commit, and push.
svg:
	$(PY) $(SCRIPT) $(DRAWIO) --git-message "$(MSG)" --push

# Export + commit (no push):
svg-nopush:
	$(PY) $(SCRIPT) $(DRAWIO) --git-message "$(MSG)"

# Dry-run:
svg-dry:
	$(PY) $(SCRIPT) $(DRAWIO) --dry-run
