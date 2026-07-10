# Finals verification entrypoint (FINALS_EXIT_CRITERIA.md §6).
# `make verify` = every machine-checkable gate; add --with-docker via
# `make verify-full` (needs Docker Desktop running).
PY ?= py

verify:
	bash scripts/run_all_tests.sh

verify-full:
	bash scripts/run_all_tests.sh --with-docker
	bash tests/e2e_cold_start.sh

.PHONY: verify verify-full
