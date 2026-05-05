#!/usr/bin/env python3
"""
Montrezor System - Launcher Avançado
Executa o app Streamlit com tratamento de erros e interface profissional
"""
import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def print_banner():
    """Exibe banner profissional"""
    print("=" * 60)
    print("    🚀 MONTREZOR SYSTEM - DASHBOARD WEB")
    print("=" * 60)
    print()

def activate_venv():
    """Ativa o ambiente virtual"""
    venv_path = Path("..") / ".venv" / "Scripts" / "Activate.bat"

    if not venv_path.exists():
        print("❌ ERRO: Ambiente virtual não encontrado!")
        print(f"   Caminho procurado: {venv_path}")
        return False

    print("🔄 [1/4] Ativando ambiente virtual...")

    # Executar activation script
    try:
        result = subprocess.run(
            [str(venv_path)],
            shell=True,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Erro ao ativar venv: {e}")
        return False

def check_dependencies():
    """Verifica e instala dependências"""
    print("🔍 [2/4] Verificando dependências...")

    required_packages = ['streamlit', 'pandas', 'plotly']
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (faltando)")
            missing_packages.append(package)

    if missing_packages:
        print(f"📦 Instalando pacotes faltantes: {', '.join(missing_packages)}")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install"
            ] + missing_packages, check=True)
            print("   ✅ Dependências instaladas!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao instalar dependências: {e}")
            return False

    return True

def start_streamlit():
    """Inicia o aplicativo Streamlit"""
    print("🚀 [3/4] Iniciando aplicação web...")
    print()
    print("⏳ Aguarde o navegador abrir automaticamente...")
    print("🛑 Para PARAR: Feche esta janela ou pressione Ctrl+C")
    print("=" * 60)
    print()

    # Tentar iniciar o Streamlit
    try:
        # Comando Streamlit
        cmd = [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", "8501",
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false"
        ]

        # Iniciar processo
        process = subprocess.Popen(cmd)

        # Aguardar um pouco e tentar abrir navegador manualmente se não abrir
        time.sleep(3)
        webbrowser.open("http://localhost:8501")

        # Aguardar o processo terminar
        process.wait()

    except KeyboardInterrupt:
        print("\n🛑 Aplicação encerrada pelo usuário.")
    except Exception as e:
        print(f"\n❌ Erro ao iniciar Streamlit: {e}")
        return False

    return True

def main():
    """Função principal"""
    try:
        # Mudar para o diretório correto
        script_dir = Path(__file__).parent
        os.chdir(script_dir)

        # Exibir banner
        print_banner()

        # Etapas de inicialização
        if not activate_venv():
            input("Pressione Enter para sair...")
            return False

        if not check_dependencies():
            input("Pressione Enter para sair...")
            return False

        if not start_streamlit():
            input("Pressione Enter para sair...")
            return False

    except KeyboardInterrupt:
        print("\n🛑 Execução interrompida.")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        input("Pressione Enter para sair...")

if __name__ == "__main__":
    main()
