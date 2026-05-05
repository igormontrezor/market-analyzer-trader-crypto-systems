#!/usr/bin/env python3
"""
Runner para o visualizador web do Market Analysis System - Versão Corrigida
Execute este arquivo da pasta analysis_system para iniciar o visualizador
"""

import subprocess
import sys
import os

def main():
    """Executa o visualizador web com porta alternativa"""
    print("🚀 Iniciando Market Analysis Web Visualizer...")
    print("📊 Baseado exatamente no notebook market_analysis_oop.ipynb")
    print("🌐 Abrindo interface web em http://localhost:8502")
    print("🔧 Usando porta 8502 (8501 ocupada)")
    print("---")
    
    # Executa o streamlit com o visualizer corrigido e porta 8502
    try:
        subprocess.run([
            "c:\\market_montrezor_system\\.venv\\Scripts\\python.exe", "-m", "streamlit", "run", 
            "web/visualizer.py",
            "--server.port", "8502",
            "--server.address", "localhost"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar streamlit: {e}")
        print("💡 Verifique se streamlit está instalado e se o arquivo existe")
    except KeyboardInterrupt:
        print("\n👋 Visualizador encerrado pelo usuário")

if __name__ == "__main__":
    main()
