@echo off
start cmd /k "cd services\scoring-api && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
start cmd /k "cd services\admin-api && npm run dev"
