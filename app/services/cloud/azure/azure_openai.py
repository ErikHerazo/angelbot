import os
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

# === CONFIGURACIÓN ===
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")  # ej. "gpt-4o-angelbot"

# === CLIENTES ===
search_client = SearchClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    index_name=AZURE_SEARCH_INDEX,
    credential=AzureKeyCredential(AZURE_SEARCH_KEY)
)

openai_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    api_version="2024-08-01-preview"  # usa versión nueva
)

# === FUNCIÓN PARA RECUPERAR DOCUMENTOS ===
def retrieve_documents(query: str, top_k=3):
    results = search_client.search(search_text=query, top=top_k)
    context = []
    for doc in results:
        content = doc.get("content") or doc.get("text") or ""
        context.append(content)
    return "\n".join(context)

# === FUNCIÓN PRINCIPAL DE RAG ===
def rag_query(user_query: str):
    retrieved_context = retrieve_documents(user_query)
    
    if not retrieved_context:
        return "No se encontró contexto relevante."

    prompt = f"""
    Eres un asistente experto. Usa el siguiente contexto para responder la pregunta.
    Si la respuesta no está en el contexto, responde educadamente que no tienes información.

    CONTEXTO:
    {retrieved_context}

    PREGUNTA:
    {user_query}
    """

    response = openai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500
    )

    return response.choices[0].message.content.strip()


# === PRUEBA ===
if __name__ == "__main__":
    query = "Cuéntame la historia de Cartagena"
    answer = rag_query(query)
    print("🧩 RESPUESTA:")
    print(answer)
