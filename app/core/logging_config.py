import logging
import sys

# Configuración básica del logger global
logger = logging.getLogger("angelbot")
logger.setLevel(logging.INFO)

# Formato de logs
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s - %(message)s", "%Y-%m-%d %H:%M:%S"
)

# Handler para consola
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)

# Evitar handlers duplicados en reloads
if not logger.handlers:
    logger.addHandler(handler)
