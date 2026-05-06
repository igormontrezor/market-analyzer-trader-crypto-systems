# 📅 AGENDAMENTO AUTOMÁTICO - INSTRUÇÕES

## 🎯 Frequências:
- **Funding Rate**: A cada 1 hora
- **Macro Timing**: A cada 4 horas  
- **Gems Finder**: A cada 12 horas

## 📁 Arquivos criados:
- `atualizar_funding.bat` - Atualiza funding rate
- `atualizar_gems.bat` - Busca gems
- `atualizar_macro.bat` - Atualiza macro timing

## 🚀 Como agendar:

1. **Abrir Agendador de Tarefas** (Win + R → `taskschd.msc`)

2. **Criar 3 tarefas**:

### 📊 Tarefa 1 - Funding Rate
- **Nome**: `GEMS_Funding_Rate`
- **Gatilho**: Diariamente → Repetir a cada **1 hora**
- **Ação**: `atualizar_funding.bat`

### 📈 Tarefa 2 - Macro Timing  
- **Nome**: `GEMS_Macro_Timing`
- **Gatilho**: Diariamente → Repetir a cada **4 horas**
- **Ação**: `atualizar_macro.bat`

### 💎 Tarefa 3 - Gems Finder
- **Nome**: `GEMS_Finder`
- **Gatilho**: Diariamente → Repetir a cada **12 horas**
- **Ação**: `atualizar_gems.bat`

## ⚙️ Configurações importantes:
- Marcar: **"Executar mesmo que o usuário não esteja conectado"**
- Marcar: **"Não parar se o computador estiver em bateria"**

## ✅ Pronto!
Sistema irá atualizar automaticamente em background.
