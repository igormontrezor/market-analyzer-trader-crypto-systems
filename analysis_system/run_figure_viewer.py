#!/usr/bin/env python3
"""
Runner para o Figure Viewer do Market Analysis System
Execute este arquivo da pasta analysis_system para iniciar o visualizador
"""

import subprocess
import sys
import os

def main():
    """Executa o figure viewer"""
    print("🚀 Iniciando Market Analysis Figure Viewer...")
    print("📊 Visualizador de Figures Compostas do notebook market_analysis_oop.ipynb")
    print("🌐 Abrindo interface web em http://localhost:8504")
    print("🎯 Cada Figure = 6 gráficos compostos com indicadores e sinais")
    print("---")
    
    # Executa o streamlit com o figure viewer
    try:
        subprocess.run([
            "c:\\market_montrezor_system\\.venv\\Scripts\\python.exe", "-m", "streamlit", "run", 
            "web/figure_viewer.py",
            "--server.port", "8504",
            "--server.address", "localhost"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar streamlit: {e}")
        print("💡 Verifique se streamlit está instalado e se o arquivo existe")
    except KeyboardInterrupt:
        print("\n👋 Visualizador encerrado pelo usuário")

if __name__ == "__main__":
    main()
