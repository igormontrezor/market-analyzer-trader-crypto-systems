import os
import glob

def limpar_cache():
    print("🧹 Iniciando a limpeza de arquivos de cache e vínculos antigos...")

    # 1. Procura por pastas __pycache__ e deleta
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            p = os.path.join(root, '__pycache__')
            import shutil
            shutil.rmtree(p)
            print(f"🗑️ Removida pasta: {p}")

    # 2. Deleta arquivos de configuração do streamlit e lixeiras locais
    arquivos_lixo = glob.glob('.streamlit', recursive=True)
    for pasta in arquivos_lixo:
        import shutil
        shutil.rmtree(pasta)
        print(f"🗑️ Removida pasta: {pasta}")

    print("✅ Limpeza concluída! Você já pode deletar o arquivo limpeza.py.")

if __name__ == "__main__":
    limpar_cache()
