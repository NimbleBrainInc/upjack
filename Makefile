.PHONY: validate-schemas test-lib test-lib-ts check clean

validate-schemas:
	$(MAKE) -C schemas validate

test-lib:
	$(MAKE) -C lib/python test

test-lib-ts:
	$(MAKE) -C lib/typescript test

check: validate-schemas test-lib test-lib-ts
	@echo "All checks passed."

clean:
	$(MAKE) -C lib/python clean
	$(MAKE) -C lib/typescript clean

# Evals (require `claude` CLI on PATH)
eval:
	$(MAKE) -C evals run
eval-smoke:
	$(MAKE) -C evals run-smoke
eval-case:
	$(MAKE) -C evals run-case CASE=$(CASE)
eval-install:
	$(MAKE) -C evals install
