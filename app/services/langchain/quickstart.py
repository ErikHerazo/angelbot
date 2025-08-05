import os
import dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser


def main():
    dotenv.load_dotenv()

    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")

    llm = AzureChatOpenAI(
        azure_deployment=deployment,
        api_version="2025-01-01-preview",
        temperature=0.0,
        max_tokens=1024,
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
                        "query_type": "semantic",
                        "semantic_configuration": "default",
                        "top_n_documents": 5,
                        "in_scope": True,
                        "fields_mapping": {
                            "content_fields": ["content"],
                            "title_field": "title"
                        }
                    }
                }
            ],
        },
        timeout=None,
        max_retries=2,
    )

    prompt = ChatPromptTemplate.from_messages([
        HumanMessagePromptTemplate.from_template("{input}")
    ])

    chain = prompt | llm | StrOutputParser()

    response = chain.invoke(
        {
            "input_language": "Spanish",
            "output_language": "Spanish",
            "input": "Quien es leonel messi?.",
        }
    )
    
    print(response)

if __name__ == "__main__":
    main()
