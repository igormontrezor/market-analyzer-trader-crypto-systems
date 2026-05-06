@echo off
call "C:\market_montrezor_system\.venv\Scripts\activate"
cd /d "C:\market_montrezor_system\gems_system"
python -c "from visualizer import _load_macro_timing; _load_macro_timing()"
call deactivate
