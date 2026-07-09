@echo off
cd /d "%~dp0backend"
set PYTHONPATH=.
echo === Gemini LLM Test ===
echo .env dosyasinda GEMINI_API_KEY tanimli olmali.
echo.
"%~dp0venv\Scripts\python.exe" -c "from config import load_env; load_env(); from llm.reporter import LLMReporter; r=LLMReporter(); import json; print(json.dumps(r.test_connection(), ensure_ascii=False, indent=2))"
echo.
pause
