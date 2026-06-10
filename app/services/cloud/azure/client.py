import os
from app.core import constants
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv


load_dotenv()
PRIMARY_KEY=os.getenv("AZURE_OPENAI_API_KEY_MAIN")

primary_client = AsyncAzureOpenAI(
    azure_endpoint=constants.BASE_URL,
    api_key=PRIMARY_KEY,
    api_version=constants.AZURE_OPENAI_API_VERSION,
    max_retries=constants.OPENAI_MAX_RETRIES
)

secondary_client = AsyncAzureOpenAI(
    azure_endpoint=constants.BASE_URL,
    api_key=PRIMARY_KEY,
    api_version=constants.AZURE_OPENAI_API_VERSION,
    max_retries=constants.OPENAI_MAX_RETRIES
)
