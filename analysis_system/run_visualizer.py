#!/usr/bin/env python3
"""
Runner para o visualizador web do Market Analysis System
Execute este arquivo da pasta analysis_system para iniciar o visualizador
"""

import subprocess
import sys
import os

def main():
    """Executa o visualizador web standalone"""
    print("🚀 Iniciando Market Analysis Web Visualizer...")
    print("📊 Baseado exatamente no notebook market_analysis_oop.ipynb")
    print("🌐 Abrindo interface web em http://localhost:8501")
    print("---")

    # Executa o streamlit com o visualizador standalone
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "web/visualizer.py"
            "--server.port", "8501",
            "--server.address", "localhost"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar streamlit: {e}")
        print("💡 Certifique-se de que streamlit está instalado: pip install streamlit")
    except KeyboardInterrupt:
        print("\n👋 Visualizador encerrado pelo usuário")

if __name__ == "__main__":
    main()
