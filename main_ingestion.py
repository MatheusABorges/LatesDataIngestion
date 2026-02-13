import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_qdrant import QdrantVectorStore
from qdrant_client import models
from qdrant_client import QdrantClient
from embedding_factory import EmbeddingHandler
from lattes_processor import LattesProcessor

# Carrega variáveis de ambiente
load_dotenv()

xml_folder = os.getenv('XML_INPUT_FOLDER')
if not xml_folder:
    raise ValueError("XML_INPUT_FOLDER not found in .env file")

print("--- INICIANDO CONFIGURAÇÃO ---")

try:
    provider_env = os.getenv("EMBEDDING_PROVIDER")
    model_env = os.getenv("EMBEDDING_MODEL_NAME")
    device_env = os.getenv("HUGGING_FACE_DEVICE", "cpu")
    api_key_env = os.getenv("EMBEDDING_API_KEY")
    if not provider_env or not model_env:
        raise ValueError("EMBEDDING_PROVIDER and EMBEDDING_MODEL must be set in .env")

    #is_ingestion=True pois estamos salvando documentos.
    embedding_handler = EmbeddingHandler(
        provider=provider_env,
        model_name=model_env,
        api_key=api_key_env,
        is_ingestion=True,
        device=device_env
    )

except Exception as e:
    print(f"Erro na inicialização do modelo: {e}")
    exit(1)

# Lista para acumular todos os documentos de todos os XMLs antes de salvar
todos_documentos = []

print(f"--- LENDO ARQUIVOS NA PASTA: {xml_folder} ---")

# 2. LOOP DE LEITURA DOS ARQUIVOS
final_chunks = []

# Loop de arquivos
for xml_file in Path(xml_folder).glob('*.xml'):
    try:
        print(f"Processando: {xml_file.name}")
        
        # Instancia o processador para este arquivo
        processor = LattesProcessor(xml_file)
        
        # Pega os chunks prontos
        chunks = processor.get_all_chunks()
        
        final_chunks.extend(chunks)
        print(f"  -> Gerou {len(chunks)} chunks.")
        
    except Exception as e:
        print(f"Erro no arquivo {xml_file}: {e}")

# Salva no Qdrant
if final_chunks:

    url_qdrant = os.getenv("QDRANT_URL")
    if not url_qdrant:
        raise ValueError("QDRANT_URL is required in .env to connect to Qdrant database")
    qdrant_client = QdrantClient(url=url_qdrant) 
    collection_name = os.getenv("QDRANT_COLLECTION_NAME", "lattes_demo")

    if not qdrant_client.collection_exists(collection_name):
        print(f"Coleção '{collection_name}' não existe. Criando...")
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=embedding_handler.dimension,
                distance=models.Distance.COSINE
            )
        )
    else:
        print(f"Coleção '{collection_name}' já existe. Adicionando dados...")

    # Adiciona os documentos ao Qdrant
    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        embedding=embedding_handler.model
    )

    # 4. Adiciona os documentos na instância criada
    vector_store.add_documents(documents=final_chunks)

    print("✅ Ingestão concluída com sucesso!")
    print(f"Visualização disponível em: {url_qdrant}/dashboard")