import os
import logging
from dotenv import load_dotenv
from app.core import constants
from app.services.cloud.azure.load_balancer import load_balancer
from app.services.cloud.azure import azure_tools


load_dotenv()
logger = logging.getLogger(__name__)

async def make_completion(messages, max_toks, force_text=False):
    """
    Make a call to Azure OpenAI ChatCompletion.
    If `force_text=True`, force tool_choice='none' to prevent further tool calls.
    """
    async def completion_request(client, deployment):
        # 🔥 LOG DEL MODELO USADO
        logger.info(
            "Executing Azure OpenAI completion",
            extra={
                "deployment": deployment,
                "max_tokens": max_toks,
                "force_text": force_text,
            }
        )
        return await client.chat.completions.create(
            model=deployment,
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
    return await load_balancer.execute(completion_request)
