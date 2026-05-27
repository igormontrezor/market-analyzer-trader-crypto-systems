# montrezor_logging.py
import logging
import sys
from datetime import datetime

# Configuração básica
_logger = None

def get_logger(name="Montrezor"):
    global _logger
    if _logger is None:
        _logger = logging.getLogger(name)
        _logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        _logger.addHandler(handler)
    return _logger

# Para uso nos módulos
logger = get_logger()
