@echo off
echo ========================================
echo 🗑️ REMOVER TUDO - GEMS SYSTEM
echo ========================================
echo.

echo 🔧 Verificando permissões...
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Execute como Administrador!
    pause
    exit /b 1
)

echo 🗑️ Removendo tarefas...
schtasks /delete /tn "GEMS_Funding_Rate" /f >nul 2>&1
schtasks /delete /tn "GEMS_Macro_Timing" /f >nul 2>&1
schtasks /delete /tn "GEMS_Finder" /f >nul 2>&1

echo ✅ Todas as tarefas removidas!
echo.
echo 🎯 Sistema limpo!
echo.
pause
