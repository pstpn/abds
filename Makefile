.PHONY: run stop clean gen load setup teardown
.DEFAULT_GOAL = run

# Starts all services in detached mode.
run:
	docker compose --env-file .env.local up -d --build

# Stops all running services.
stop:
	docker compose --env-file .env.local down

# Stops all services and removes volumes.
clean:
	docker compose --env-file .env.local down -v

# Generates CSV datasets into data/.
gen:
	python3 scripts/generate.py

# Loads datasets from data/ into ClickHouse. Requires a running ClickHouse (make run).
load:
	python3 scripts/load.py

# Creates the schema, generates and loads the data. Requires a running ClickHouse (make run).
setup:
	python3 scripts/schema.py
	$(MAKE) gen
	$(MAKE) load

# Drops the tables and the data.
teardown:
	python3 scripts/teardown.py
