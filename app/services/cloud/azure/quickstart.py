import os
import openai
import dotenv

dotenv.load_dotenv()

endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT_MAIN")
api_key = os.environ.get("AZURE_OPENAI_API_KEY_MAIN")
deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME_MAIN")

client = openai.AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version="2025-01-01-preview",
)

completion = client.chat.completions.create(
    model=deployment,
    messages=[
        {
            "role": "user",
            "content": "Quienes son lo smedicos de la clinica?",
        },
    ],
    max_tokens=1024,
    temperature=0.0,
    extra_body={
        "data_sources":[
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
    }
)

print(f"{completion.choices[0].message.role}: {completion.choices[0].message.content}")
