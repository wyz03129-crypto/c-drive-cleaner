$ErrorActionPreference = "Stop"

python -m ruff check .
if ($LASTEXITCODE -ne 0) { throw "Lint failed" }
python -m ruff format --check src/cdrive_cleaner scripts tests
if ($LASTEXITCODE -ne 0) { throw "Format check failed" }
python -m mypy
if ($LASTEXITCODE -ne 0) { throw "Type check failed" }
python -m pytest
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
python scripts/check_mutation_gate.py
if ($LASTEXITCODE -ne 0) { throw "Mutation gate failed" }
python scripts/release_gate.py
if ($LASTEXITCODE -ne 0) { throw "Release gate failed" }
