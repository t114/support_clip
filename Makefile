PYTHON = ./venv/bin/python
UVICORN = ./venv/bin/uvicorn
PID_FILE = backend.pid
LOG_FILE = backend.log

.PHONY: start stop restart logs status help

help:
	@echo "Available commands:"
	@echo "  make start    - Start the backend server in background"
	@echo "  make stop     - Stop the backend server"
	@echo "  make restart  - Restart the backend server"
	@echo "  make logs     - View server logs (Ctrl+C to exit)"
	@echo "  make status   - Check if server is running"

start:
	@echo "Stopping any existing server..."
	@$(MAKE) -s stop
	@echo "Starting backend server..."
	@nohup $(UVICORN) backend.main:app --reload --host 0.0.0.0 --port 8000 --log-config log_config.ini > $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE)
	@echo "Server started. Run 'make logs' to view output."

stop:
	@lsof -t -i:8000 | xargs -r kill -9
	@rm -f $(PID_FILE)
	@echo "Server stopped."

restart: stop start

logs:
	@tail -f $(LOG_FILE)

status:
	@if lsof -i:8000 > /dev/null; then echo "Server is running."; else echo "Server is NOT running."; fi
