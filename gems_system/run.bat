@echo off
echo =======================================
echo MARKET MONTREZOR SYSTEM - GEMS FINDER v7.1
echo Sistema Multi-Timeframe com Social Intelligence REAL
echo    TradingView Data + Macro Timing Automatizado + Tutoriais Profissionais
echo =======================================
echo.

echo Verificando estrutura de diretorios...
if not exist "data" mkdir "data" >nul 2>&1
if not exist "data\daily_snapshots" mkdir "data\daily_snapshots" >nul 2>&1
if not exist "data\snapshots" mkdir "data\snapshots" >nul 2>&1
echo Diretorios OK!
echo.

echo Verificando configuracoes de API...
if not exist "..\config\api_keys.py" (
    echo ⚠️  YouTube API nao encontrada (usara simulacao)
) else (
    echo ✅ YouTube API encontrada
)
if not exist "telegram_config.py" (
    echo ⚠️  Telegram config nao encontrado (usara simulacao)
) else (
    echo ✅ Telegram config encontrado
)
echo.

echo Ativando ambiente virtual...
cd ..
call .venv\Scripts\activate.bat 2>nul
if errorlevel 1 (
    echo Erro ao ativar ambiente virtual
    pause
    exit /b 1
)

echo Executando GEMS FINDER v7.1...
echo    - TradingView Integration: USDT.D + OTHERS dados reais
echo    - Macro Timing Automatico: Cache 1 hora, BB%B calculos
echo    - Tutoriais Profissionais: Bubble Chart, Acumulação, Heatmap
echo    - Social Intelligence: YouTube API + Telegram Scraping
echo    - Sistema Production-Ready: Cache 12h, arquivos otimizados
echo.

cd gems_system
python gems_finder.py
if errorlevel 1 (
    echo Erro durante execucao
    pause
    exit /b 1
)

echo.
echo ✅ GEMS FINDER v7.1 CONCLUIDO!
echo.
echo 📁 Arquivos gerados (se aplicavel):
echo    data\snapshots\gems_10M_to_50M_*.csv - Dados consolidados
echo    data\snapshots\gems_10M_to_50M_enhanced_*.csv - Com eventos especiais
echo    data\daily_snapshots\ - Snapshots diarios JSON
echo    data\gems_cache.json - Cache API (12 horas)
echo    data\macro\macro_timing.json - Macro timing (1 hora)
echo.

:menu
echo ========================================
echo ESCOLHA A PROXIMA ACAO:
echo 1. � Executar Dashboard Interativo (Visualizer)
echo 2. 🔄 Executar GEMS FINDER novamente
echo 3. 🚪 Sair
echo ========================================
set /p choice="Opcao (1-3): "

if "%choice%"=="1" goto visualizer
if "%choice%"=="2" goto rerun
if "%choice%"=="3" goto exit
echo Opcao invalida! Tente novamente.
goto menu

:visualizer
echo.
echo 🚀 Executando Dashboard Interativo...
echo ========================================
echo MARKET MONTREZOR SYSTEM - VISUALIZADOR v7.1
echo Dashboard Interativo com TradingView Integration
echo    Macro Timing Automatizado + Tutoriais Profissionais
echo    Bubble Chart + Acumulação Silenciosa + Heatmap Setorial
echo ========================================
cd /d "%~dp0"
echo 📂 Diretório: %CD%
echo.
echo 🚀 Executando visualizer com TradingView data...
c:\market_montrezor_system\.venv\Scripts\python.exe visualizer.py
goto menu

:rerun
echo.
echo 🔄 Executando GEMS FINDER novamente...
cd ..
cd gems_system
python gems_finder.py
if errorlevel 1 (
    echo Erro durante execucao
    pause
    exit /b 1
)
goto menu

:exit
echo.
echo 👋 Até logo!
pause
exit /b 0
