import os
from openai import AzureOpenAI


def get_azure_openai_client() -> AzureOpenAI:
    """
    Crea y devuelve un cliente de Azure OpenAI configurado con las credenciales
    y el endpoint especificados en las variables de entorno.

    Variables de entorno necesarias:
        - AZURE_OPENAI_ENDPOINT: URL del recurso Azure OpenAI.
        - AZURE_OPENAI_API_KEY: Clave de API para autenticar el cliente.

    Returns:
        AzureOpenAI: Instancia del cliente listo para realizar llamadas a la API.
    """
    # Obtenemos la URL del endpoint de Azure OpenAI desde las variables de entorno
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    
    # Obtenemos la clave de API desde las variables de entorno
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    # Creamos la instancia del cliente Azure OpenAI con la versión de API deseada
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2025-01-01-preview"  # Versión de la API que se está utilizando
    )

    return client
