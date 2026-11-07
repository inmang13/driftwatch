# DriftWatch Makefile. Works on Windows (make from PowerShell -> cmd.exe) and Linux (Orange Pi).
# Keep every recipe to plain single commands: no export/source/shell-if, so cmd.exe and sh both run them.

ifeq ($(OS),Windows_NT)
PYTHON ?= python
PY := .venv\Scripts\python.exe
else
PYTHON ?= python3
PY := .venv/bin/python
endif

SOURCE ?= snapshot
SITE ?= 03459500
LLM ?=

.PHONY: install snapshot report run serve test evals demo

$(PY):
	$(PYTHON) -m venv .venv

install: $(PY)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev,agents,api]"

# Site list lives in driftwatch/modules/rating_curve/usgs.py (SITES). Refuses unless SOURCE=live (the fetcher enforces it): make snapshot SOURCE=live
snapshot:
	$(PY) -m driftwatch.modules.rating_curve.usgs --source $(SOURCE)

report:
	$(PY) -m driftwatch.cli report --site $(SITE) --source $(SOURCE)

# LLM empty -> the CLI reads LLM from .env / the shell. make run SITE=03455000 LLM=fallback
run:
	$(PY) -m driftwatch.cli run --site $(SITE) --llm "$(LLM)"

serve:
	@echo not yet: make serve

test:
	$(PY) -m pytest -q

evals:
	@echo not yet: make evals

# Demo must pass offline: the agent runs are pinned to the deterministic fallback.
demo:
	$(PY) -m driftwatch.cli report --site 03459500 --source snapshot
	$(PY) -m driftwatch.cli report --site 03451000 --source snapshot
	$(PY) -m driftwatch.cli run --site 03459500 --llm fallback
	$(PY) -m driftwatch.cli run --site 03451000 --llm fallback
