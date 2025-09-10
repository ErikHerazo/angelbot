import os
import dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langdetect import detect
from app.core import constants


dotenv.load_dotenv()

async def query_langchain_with_search(user_question: str) -> str:
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")

    # Detectar idioma y mapear a nombre completo
    detected_lang = detect(user_question)
    user_lang = constants.LANG_MAP.get(detected_lang, "the same language as the question")
    
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(constants.ASSISTANT_PROMPT),
        HumanMessagePromptTemplate.from_template("{input}")
    ])

    llm = AzureChatOpenAI(
        azure_deployment=deployment,
        api_version=constants.AZURE_OPENAI_API_VERSION,
        temperature=constants.OPENAI_TEMPERATURE,
        max_tokens=constants.OPENAI_MAX_TOKENS,
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
                        "query_type": "vector_semantic_hybrid",
                        "semantic_configuration": "default",
                        "top_n_documents": 5,
                        "in_scope": True,
                        "fields_mapping": {
                            "content_fields": ["content"],
                            "title_field": "title"
                        },
                        "embedding_dependency": {
                            "type": "deployment_name",
                            "deployment_name": os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
                        }
                    }
                }
            ],
        },
        timeout=constants.OPENAI_TIMEOUT,
        max_retries=constants.OPENAI_MAX_RETRIES,
    )

    chain = prompt | llm | StrOutputParser()

    response = await chain.ainvoke({
        "input": user_question,
        "language": user_lang
    })

    return response
