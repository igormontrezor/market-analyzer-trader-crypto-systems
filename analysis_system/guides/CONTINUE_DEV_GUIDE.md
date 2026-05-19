# Continue.dev — Guia Rápido de Contexto

## Como passar contexto para o modelo

| Comando | O que faz | Quando usar |
|---------|-----------|-------------|
| `@codebase` | Busca semântica em todo o projeto indexado | Perguntas sobre o projeto inteiro |
| `@file` | Seleciona um arquivo específico | Quando sabe exatamente qual arquivo |
| `@folder` | Passa uma pasta inteira | Quando quer focar num módulo |
| `@diff` | Mostra o que mudou no git | Revisar alterações recentes |
| `@terminal` | Último output do terminal | Depurar erros do console |
| `@problems` | Erros/warnings do editor | Corrigir erros do VS Code |
| `@open` | Todos os arquivos abertos nas abas | Contexto do que está trabalhando |

## Exemplos práticos

### Buscar no projeto inteiro
```
@codebase como funciona o check_signals?
@codebase onde é chamado o send_telegram?
```

### Arquivo específico
```
@trading_system.py explica a função enrich_signal
@montrezor_daemon.py @trading_system.py as lógicas estão iguais?
```

### Pasta inteira
```
@folder /meu-projeto explica a estrutura geral
```

### Depurar erro do terminal
```
@terminal o que causou esse erro?
```

### Corrigir warnings do editor
```
@problems corrija todos os erros listados
```

## Modo Agent (edita arquivos sozinho)

- Troque para **Agent** no dropdown do painel do Continue.
- Nesse modo ele busca os arquivos automaticamente — não precisa de `@`.
- **Atalho padrão**: `Ctrl+Shift+I` (se conflitar com Copilot, troque em: `Ctrl+Shift+P` → Keyboard Shortcuts → busca "continue")

## Selecionar trecho e perguntar

1. Selecione o código com o mouse
2. `Ctrl+L` — abre o chat com aquele trecho já incluído
3. Faça a pergunta normalmente

**Sem digitar nada**: O arquivo aberto e visível no editor é incluído automaticamente. Basta perguntar sem `@` para comentários sobre o arquivo atual.

## Forçar re-indexação do projeto

Se o `@codebase` não estiver achando arquivos novos:
`Ctrl+Shift+P` → **Continue: Rebuild codebase index**
