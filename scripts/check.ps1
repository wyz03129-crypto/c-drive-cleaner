$ErrorActionPreference = "Stop"

python -m ruff check .
python -m ruff format --check src/cdrive_cleaner scripts tests
python -m mypy
python -m pytest
python scripts/check_mutation_gate.py
