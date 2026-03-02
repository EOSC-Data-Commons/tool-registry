export PYTHONPATH := $(PWD)/src:$(PYTHONPATH)
PORT ?= 8080
HOST_PORT ?= 8080

.PHONY: run sync force-sync install
run: sync
	uvicorn src.main:app --host 0.0.0.0 --port $(PORT) --reload

install:
	mkdir -p cache
	uv sync --frozen --no-cache

.PHONY: re-install install
re-install: clean sync

.PHONY: clean
clean:
	uv clean
	rm uv.lock
	rm -rf .venv/lib/python3.12/site-packages/toolmeta_models/

sync:
	uv sync 

force-sync:
	rm uv.lock
	uv sync --force-reinstall

build-docker:
	docker build -t tool-registry:latest .

run-docker:
	docker run -e PORT=$(PORT) -p $(HOST_PORT):$(PORT)  -v ./config:/app/config tool-registry:latest

