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
	@nohup $(UVICORN) backend.main:app --reload --reload-dir backend --host 0.0.0.0 --port 8000 --log-config log_config.ini \
		--reload-exclude "backend/uploads/*" \
		--reload-exclude "*/__pycache__/*" \
		> $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE)
	@echo "Server started. Run 'make logs' to view output."

stop:
	@echo "Stopping backend server..."
	@if [ -f $(PID_FILE) ]; then \
		kill $$(cat $(PID_FILE)) 2>/dev/null || true; \
	fi
	@-lsof -t -i:8000 | xargs -r kill -9 2>/dev/null || true
	@-pkill -f "uvicorn backend.main:app" 2>/dev/null || true
	@$(MAKE) -s kill-ffmpeg
	@rm -f $(PID_FILE)
	@echo "Waiting for port 8000 to be released..."
	@for i in 1 2 3 4 5; do \
		if ! lsof -i:8000 > /dev/null; then \
			break; \
		fi; \
		sleep 1; \
	done
	@echo "Server stopped."

kill-ffmpeg:
	@echo "Killing lingering ffmpeg processes..."
	@pkill -9 ffmpeg || echo "No ffmpeg processes found."

restart: stop start

logs:
	@tail -f $(LOG_FILE)

status:
	@if lsof -i:8000 > /dev/null; then echo "Server is running."; else echo "Server is NOT running."; fi
