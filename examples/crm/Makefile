VERSION ?= 1.0.0

.PHONY: help bundle clean run

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

bundle: ## Build MCPB bundle
	@./scripts/build-bundle.sh $(VERSION)

run: bundle ## Build and run with mpak
	@mpak run --local *.mcpb

clean: ## Remove build artifacts
	rm -rf deps/ *.mcpb
