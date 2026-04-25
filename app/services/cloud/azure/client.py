import os
from app.core import constants
from openai import AsyncAzureOpenAI


def get_azure_openai_client() -> AsyncAzureOpenAI:
    """
    Creates and returns an Azure OpenAI client configured with the credentials and endpoint specified in the environment variables.
    Required environment variables:
    # - AZURE_OPENAI_ENDPOINT_MAIN: URL of the Azure OpenAI resource.
    - OPENAI_BASE_URL: URL of the APIM.
    - AZURE_OPENAI_API_KEY_MAIN: API key to authenticate the client.
    Returns:
    AsyncAzureOpenAI: Client instance ready to make API calls.
    """
    # Obtain the Azure OpenAI endpoint URL from the environment variables
    endpoint = os.getenv("OPENAI_BASE_URL")
    
    # Obtain the API key from the environment variables
    api_key = os.getenv("API_KEY")

    # Create the Azure OpenAI client instance with the desired API version
    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=constants.AZURE_OPENAI_API_VERSION
    )

    return client
