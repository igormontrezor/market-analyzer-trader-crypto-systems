@echo off
call "C:\market_montrezor_system\.venv\Scripts\activate"
cd /d "C:\market_montrezor_system\gems_system"
python funding_only.py
call deactivate
