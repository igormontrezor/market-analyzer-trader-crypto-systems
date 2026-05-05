#!/usr/bin/env python3
"""
Runner para o Notebook Viewer do Market Analysis System
Execute este arquivo da pasta analysis_system para iniciar o visualizador
"""

import subprocess
import sys
import os

def main():
    """Executa o notebook viewer"""
    print("🚀 Iniciando Market Analysis Notebook Viewer...")
    print("📊 Reproduz EXATAMENTE os gráficos do notebook market_analysis_oop.ipynb")
    print("🌐 Abrindo interface web em http://localhost:8503")
    print("🎯 Gráficos idênticos ao notebook com seleção fácil")
    print("---")
    
    # Executa o streamlit com o notebook viewer
    try:
        subprocess.run([
            "c:\\market_montrezor_system\\.venv\\Scripts\\python.exe", "-m", "streamlit", "run", 
            "web/notebook_viewer.py",
            "--server.port", "8503",
            "--server.address", "localhost"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar streamlit: {e}")
        print("💡 Verifique se streamlit está instalado e se o arquivo existe")
    except KeyboardInterrupt:
        print("\n👋 Visualizador encerrado pelo usuário")

if __name__ == "__main__":
    main()
