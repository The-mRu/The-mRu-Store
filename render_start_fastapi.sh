#!/usr/bin/env bash
uvicorn main_db_server:app --host 0.0.0.0 --port $PORT