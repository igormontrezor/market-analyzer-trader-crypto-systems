@echo off
echo ========================================
echo 🚀 INSTALADOR AUTOMÁTICO GEMS SYSTEM
echo ========================================
echo.

echo 🔧 Verificando permissões de Administrador...
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Execute como Administrador!
    echo.
    echo Botão direito no arquivo → Executar como Administrador
    pause
    exit /b 1
)

echo ✅ Permissões OK
echo.

echo 📊 Criando tarefa Funding Rate (1 hora)...
schtasks /create /tn "GEMS_Funding_Rate" /tr "C:\market_montrezor_system\gems_system\atualizar_funding.bat" /sc daily /st 00:00 /du 24:00 /ri 60 /f
if %errorlevel% equ 0 (
    echo ✅ Funding Rate criado
) else (
    echo ❌ Erro no Funding Rate
)

echo.
echo 📈 Criando tarefa Macro Timing (4 horas)...
schtasks /create /tn "GEMS_Macro_Timing" /tr "C:\market_montrezor_system\gems_system\atualizar_macro.bat" /sc daily /st 00:00 /du 24:00 /ri 240 /f
if %errorlevel% equ 0 (
    echo ✅ Macro Timing criado
) else (
    echo ❌ Erro no Macro Timing
)

echo.
echo 💎 Criando tarefa Gems Finder (12 horas)...
schtasks /create /tn "GEMS_Finder" /tr "C:\market_montrezor_system\gems_system\atualizar_gems.bat" /sc daily /st 08:00 /du 24:00 /ri 720 /f
if %errorlevel% equ 0 (
    echo ✅ Gems Finder criado
) else (
    echo ❌ Erro no Gems Finder
)

echo.
echo 🔧 Configurando para rodar mesmo com PC em bateria...
schtasks /change /tn "GEMS_Funding_Rate" /ru SYSTEM /rp
schtasks /change /tn "GEMS_Macro_Timing" /ru SYSTEM /rp  
schtasks /change /tn "GEMS_Finder" /ru SYSTEM /rp

echo.
echo ========================================
echo 🎯 INSTALAÇÃO CONCLUÍDA!
echo ========================================
echo.
echo 📋 Tarefas criadas:
echo   📊 GEMS_Funding_Rate (a cada 1 hora)
echo   📈 GEMS_Macro_Timing (a cada 4 horas)
echo   💎 GEMS_Finder (a cada 12 horas)
echo.
echo 🔍 Para verificar:
echo   Win + R → taskschd.msc
echo.
echo ✅ Sistema pronto para operação automática!
echo.
pause
