# ========================================
# MARKET MONTREZOR SYSTEM - GEMS FINDER v7.1
# ========================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MARKET MONTREZOR SYSTEM - GEMS FINDER v7.1" -ForegroundColor Cyan
Write-Host "Sistema Multi-Timeframe com Social Intelligence REAL" -ForegroundColor Yellow
Write-Host "   TradingView Data + Macro Timing Automatizado + Tutoriais Profissionais" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar estrutura de diretorios
Write-Host "Verificando estrutura de diretorios..." -ForegroundColor Magenta
if (!(Test-Path "data")) { New-Item -ItemType Directory -Path "data" }
if (!(Test-Path "data\daily_snapshots")) { New-Item -ItemType Directory -Path "data\daily_snapshots" }
if (!(Test-Path "data\snapshots")) { New-Item -ItemType Directory -Path "data\snapshots" }
Write-Host "Diretorios OK!" -ForegroundColor Green
Write-Host ""

# Verificar configuracoes de API
Write-Host "Verificando configuracoes de API..." -ForegroundColor Magenta
$apiConfigExists = Test-Path "..\config\api_keys.py"
$telegramConfigExists = Test-Path "telegram_config.py"

if (-not $apiConfigExists) {
    Write-Host "⚠️  YouTube API nao encontrada (usara simulacao)" -ForegroundColor Yellow
} else {
    Write-Host "✅ YouTube API encontrada" -ForegroundColor Green
}

if (-not $telegramConfigExists) {
    Write-Host "⚠️  Telegram config nao encontrado (usara simulacao)" -ForegroundColor Yellow
} else {
    Write-Host "✅ Telegram config encontrado" -ForegroundColor Green
}
Write-Host ""

# Ir para o diretório principal
Set-Location ".."

# Ativar venv
try {
    & ".\.venv\Scripts\Activate.ps1"
    Write-Host "Ambiente virtual ativado!" -ForegroundColor Green
} catch {
    Write-Host "Erro ao ativar ambiente virtual" -ForegroundColor Red
    Read-Host 'Pressione Enter para continuar'
    exit
}

Write-Host "Executando GEMS FINDER v7.1..." -ForegroundColor Yellow
Write-Host "   - TradingView Integration: USDT.D + OTHERS dados reais" -ForegroundColor Cyan
Write-Host "   - Macro Timing Automatico: Cache 1 hora, BB%B calculos" -ForegroundColor Cyan
Write-Host "   - Tutoriais Profissionais: Bubble Chart, Acumulação, Heatmap" -ForegroundColor Cyan
Write-Host "   - Social Intelligence: YouTube API + Telegram Scraping" -ForegroundColor Cyan
Write-Host "   - Sistema Production-Ready: Cache 12h, arquivos otimizados" -ForegroundColor Cyan
Write-Host ""

# Ir para gems_system e executar
Set-Location "gems_system"
try {
    python gems_finder.py
    Write-Host "" -ForegroundColor White
    Write-Host "✅ GEMS FINDER v7.1 CONCLUIDO!" -ForegroundColor Green
    Write-Host "" -ForegroundColor White

    Write-Host "📁 Arquivos gerados (se aplicavel):" -ForegroundColor Yellow
    Write-Host "   data\snapshots\gems_10M_to_50M_*.csv - Dados consolidados" -ForegroundColor White
    Write-Host "   data\snapshots\gems_10M_to_50M_enhanced_*.csv - Com eventos especiais" -ForegroundColor White
    Write-Host "   data\daily_snapshots\ - Snapshots diarios JSON" -ForegroundColor White
    Write-Host "   data\gems_cache.json - Cache API (12 horas)" -ForegroundColor White
    Write-Host "   data\macro\macro_timing.json - Macro timing (1 hora)" -ForegroundColor White
    Write-Host "" -ForegroundColor White

    Write-Host "💡 Para executar o dashboard interativo:" -ForegroundColor Cyan
    Write-Host "   run_visualizer.bat" -ForegroundColor White
    Write-Host "" -ForegroundColor White

} catch {
    Write-Host "Erro durante execucao do GEMS FINDER" -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
}

Write-Host ""
Read-Host 'Pressione Enter para continuar'
