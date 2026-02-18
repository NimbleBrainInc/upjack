.PHONY: install format format-check lint typecheck test build check clean copy-schema

install:
	npm install

format:
	npx biome format --write src/ tests/

format-check:
	npx biome format src/ tests/

lint:
	npx biome lint src/ tests/

typecheck:
	npx tsc --noEmit

test:
	npx vitest run

build:
	npx tsup

check: format-check lint typecheck test

clean:
	rm -rf dist node_modules

copy-schema:
	cp ../../schemas/v1/upjack-entity.schema.json src/schemas/
