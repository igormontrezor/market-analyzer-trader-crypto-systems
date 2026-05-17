@echo off
cd /d %~dp0
title Montrezor System - Iniciando Dashboard...
color 0A

echo ==========================================
echo    MONTREZOR SYSTEM - DASHBOARD WEB
echo ==========================================
echo.

:: Ativar ambiente virtual
echo [1/4] Ativando ambiente virtual...
call C:\market_montrezor_system\.venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERRO: Nao foi possivel ativar o ambiente virtual!
    echo Verifique se o arquivo .venv\Scripts\activate.bat existe.
    pause
    exit /b 1
)

:: Verificar se o Streamlit esta instalado
echo [2/4] Verificando dependencias...
python -c "import streamlit" 2>nul
if %errorlevel% neq 0 (
    echo Instalando Streamlit...
    pip install streamlit
)

:: Iniciar o aplicativo
echo [3/4] Iniciando aplicacao web...
echo.
echo Aguarde o navegador abrir automaticamente...
echo.
echo Para PARAR: Feche esta janela ou pressione Ctrl+C
echo ==========================================
echo.

:: Tentar portas até encontrar uma disponível
set PORT=8501
:check_port
netstat -an | findstr ":%PORT%" >nul
if %errorlevel% == 0 (
    echo Porta %PORT% em uso, tentando proxima...
    set /a PORT+=3
    goto check_port
)

:: Executar o Streamlit
echo Iniciando na porta %PORT%...
python -m streamlit run app.py --server.port %PORT% --server.headless false

:: Abrir navegador automaticamente
start http://localhost:%PORT%

:: Manter janela aberta em caso de erro
if %errorlevel% neq 0 (
    echo.
    echo ERRO: Ocorreu um problema ao iniciar o aplicativo!
    echo.
    pause
)
