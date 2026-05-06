@echo off
echo ========================================
echo 🔍 VERIFICAR TAREFAS GEMS SYSTEM
echo ========================================
echo.

echo 📊 Verificando GEMS_Funding_Rate...
schtasks /query /tn "GEMS_Funding_Rate" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ GEMS_Funding_Rate ATIVA
    schtasks /query /tn "GEMS_Funding_Rate" | find "Próxima"
) else (
    echo ❌ GEMS_Funding_Rate não encontrada
)

echo.
echo 📈 Verificando GEMS_Macro_Timing...
schtasks /query /tn "GEMS_Macro_Timing" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ GEMS_Macro_Timing ATIVA
    schtasks /query /tn "GEMS_Macro_Timing" | find "Próxima"
) else (
    echo ❌ GEMS_Macro_Timing não encontrada
)

echo.
echo 💎 Verificando GEMS_Finder...
schtasks /query /tn "GEMS_Finder" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ GEMS_Finder ATIVA
    schtasks /query /tn "GEMS_Finder" | find "Próxima"
) else (
    echo ❌ GEMS_Finder não encontrada
)

echo.
echo ========================================
echo 🎯 VERIFICAÇÃO CONCLUÍDA
echo ========================================
echo.
pause
