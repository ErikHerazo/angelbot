import os
from app.core import constants
from app.services.cloud.azure.client import get_azure_openai_client
from app.services.cloud.azure import azure_tools


client = get_azure_openai_client()
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME_MAIN")

async def make_completion(messages, max_toks, force_text=False):
    """
    Make a call to Azure OpenAI ChatCompletion.
    If `force_text=True`, force tool_choice='none' to prevent further tool calls.
    """
    return await client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        tools=azure_tools.tools,
        tool_choice="none" if force_text else "auto",
        temperature=constants.OPENAI_TEMPERATURE,
        max_tokens=max_toks,
        extra_body={
            "data_sources": [
                {
                    "type": "azure_search",
                    "parameters": {
                        "endpoint": os.environ["AZURE_AI_SEARCH_ENDPOINT"],
                        "index_name": os.environ["AZURE_AI_SEARCH_INDEX"],
                        "authentication": {
                            "type": "api_key",
                            "key": os.environ["AZURE_AI_SEARCH_API_KEY"],
                        },
                        "semantic_configuration": os.environ["SEMANTIC_CONFIGURATION"],
                        "fields_mapping": {
                            "content_fields": ["chunk"],
                            "title_field": "title"
                        },
                        "embedding_dependency": {
                            "type": "deployment_name",
                            "deployment_name": os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
                        },
                        "in_scope": True
                    },
                },
            ]
        },
    )
