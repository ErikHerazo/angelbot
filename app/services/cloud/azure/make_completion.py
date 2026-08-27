import os
import logging
from dotenv import load_dotenv
from app.core import constants
from app.services.cloud.azure.load_balancer import load_balancer
from app.services.cloud.azure import azure_tools


load_dotenv()
logger = logging.getLogger(__name__)

async def make_completion(messages, max_toks, force_text=False, use_data_sources=True):
    """
    Make a call to Azure OpenAI ChatCompletion.
    If `force_text=True`, force tool_choice='none' to prevent further tool calls.
    If `use_data_sources=False`, skip the "on your data" Azure Search grounding
    entirely -- para llamadas que no necesitan RAG (ej. redactar una pregunta
    aclaratoria) y donde el contenido recuperado puede dominar la respuesta por
    encima de las instrucciones del propio mensaje de sistema.
    """
    async def completion_request(client, deployment):
        # 🔥 LOG DEL MODELO USADO
        logger.info(
            "Executing Azure OpenAI completion",
            extra={
                "deployment": deployment,
                "max_tokens": max_toks,
                "force_text": force_text,
                "use_data_sources": use_data_sources,
            }
        )
        kwargs = {}
        if use_data_sources:
            kwargs["extra_body"] = {
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
            }
        return await client.chat.completions.create(
            model=deployment,
            messages=messages,
            tools=azure_tools.tools,
            tool_choice="none" if force_text else "auto",
            temperature=constants.OPENAI_TEMPERATURE,
            max_tokens=max_toks,
            **kwargs,
        )
    return await load_balancer.execute(completion_request)
