export PYTHONPATH := $(PWD)/src:$(PYTHONPATH)
PORT ?= 8000

run:
	uvicorn src.main:app --host 0.0.0.0 --port $(PORT) --reload
