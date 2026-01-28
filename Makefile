export PYTHONPATH := $(PWD)/src:$(PYTHONPATH)
PORT ?= 8080

.PHONY: run sync force-sync install
run: sync
	uvicorn src.main:app --host 0.0.0.0 --port $(PORT) --reload

install:
	uv sync --frozen --no-cache

sync:
	uv sync 

force-sync:
	rm uv.lock
	uv sync --force-reinstall

build-docker:
	docker build -t tool-registry:latest .

run-docker:
	docker run -e PORT=$(PORT) -v ./config:/app/config tool-registry:latest

