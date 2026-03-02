import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_qdrant import QdrantVectorStore
from qdrant_client import models, QdrantClient
from embedding_factory import EmbeddingHandler
from lattes_processor import LattesProcessor
from datetime import datetime

load_dotenv()

# Configurações do Ambiente
xml_folder = os.getenv('XML_INPUT_FOLDER')
url_qdrant = os.getenv("QDRANT_URL")
# Duas coleções separadas
col_summary = os.getenv("QDRANT_COL_SUMMARY", "researchers_summary")
col_data = os.getenv("QDRANT_COL_DATA", "researchers_data")

if not xml_folder or not url_qdrant:
    raise ValueError("Verifique as variáveis de ambiente XML_INPUT_FOLDER e QDRANT_URL")

print("--- INICIANDO SISTEMA DE INGESTÃO HÍBRIDA ---")

# 1. Inicializa Embeddings (Denso + Esparso)
try:
    handler_denso = EmbeddingHandler(
        provider=os.getenv("EMBEDDING_PROVIDER"),
        model_name=os.getenv("EMBEDDING_MODEL_NAME"),
        api_key=os.getenv("EMBEDDING_API_KEY"),
        device=os.getenv("HUGGING_FACE_DEVICE", "cpu")
    )
    model_esparso = EmbeddingHandler.get_sparse_model()
except Exception as e:
    print(f"Erro na inicialização dos modelos: {e}")
    exit(1)

# 2. Inicializa Cliente Qdrant
client = QdrantClient(url=url_qdrant)

def format_date_lattes(date_str):
    """
    Converte a string 'DDMMAAAA' do XML Lattes para um objeto datetime real.
    Retorna uma data muito antiga (1900) se a string for inválida, 
    para garantir que a comparação funcione (o XML novo ganhará).
    """
    if date_str and len(date_str) == 8:
        try:
            # %d = Dia, %m = Mês, %Y = Ano (4 dígitos)
            return datetime.strptime(date_str, "%d%m%Y")
        except ValueError:
            pass
            
    return datetime(1900, 1, 1)

def check_and_clean(id_lattes, xml_date):
    """
    Verifica se precisa atualizar. Se sim, deleta dados antigos.
    Retorna True se deve processar a ingestão.
    """
    # Verifica a data salva no perfil do pesquisador
    try:
        results = client.scroll(
            collection_name=col_summary,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="metadata.id_lattes", match=models.MatchValue(value=id_lattes))]
            ),
            limit=1,
            with_payload=True
        )[0]
        
        if results:
            stored_date = results[0].payload.get("metadata", {}).get("data_ingestao", "01012000")
            
            if format_date_lattes(xml_date) <= datetime.fromisoformat(stored_date):
                print(f"  [SKIP] Currículo {id_lattes} já atualizado ({xml_date}).")
                return False
            
            print(f"  [UPDATE] Nova versão detectada ({xml_date} > {stored_date}). Limpando registros antigos...")
            
            # Deleta das DUAS coleções
            filtro_id = models.Filter(must=[models.FieldCondition(key="metadata.id_lattes", match=models.MatchValue(value=id_lattes))])
            client.delete(collection_name=col_summary, points_selector=filtro_id)
            client.delete(collection_name=col_data, points_selector=filtro_id)
            return True
            
    except Exception as e:
        # Se der erro (ex: coleção não existe), assume que é novo
        print(f"Erro ao verificar dados existentes: {e}")
        pass
    
    print(f"  [NEW] Novo pesquisador encontrado: {id_lattes}")
    return True

# 3. LOOP DE PROCESSAMENTO
docs_summary = []
docs_data = []

print(f"--- LENDO ARQUIVOS NA PASTA: {xml_folder} ---")

for xml_file in Path(xml_folder).glob('*.xml'):
    try:
        # Parse inicial para pegar ID e Data
        processor = LattesProcessor(xml_file)
        
        if not (processor.researcher_info and processor.researcher_info.get('id_lattes') and processor.researcher_info.get('atualizacao') and processor.researcher_info.get('nome')):
            print(f"  [ERRO] Informações mínimas não presentes no XML: {xml_file.name}")
            continue

        # Verifica lógica de atualização
        if not check_and_clean(processor.researcher_info['id_lattes'], processor.researcher_info['atualizacao']):
            continue

        # Gera documentos
        docs_summary.append(processor.get_profile_doc())
        docs_data.extend(processor.get_production_docs())
        
        print(f"  -> Processado: {processor.researcher_info['nome']}")
        
    except Exception as e:
        print(f"Erro no arquivo {xml_file.name}: {e}")

# 4. SALVAMENTO HÍBRIDO NO QDRANT
if docs_summary:
    print(f"\nInserindo {len(docs_summary)} Perfis em '{col_summary}'...")
    QdrantVectorStore.from_documents(
        docs_summary,
        embedding=handler_denso.model,
        sparse_embedding=model_esparso, # Habilita Híbrido
        url=url_qdrant,
        collection_name=col_summary,
        retrieval_mode="hybrid",
        force_recreate=False
    )

if docs_data:
    print(f"Inserindo {len(docs_data)} Itens de Produção em '{col_data}'...")
    QdrantVectorStore.from_documents(
        docs_data,
        embedding=handler_denso.model,
        sparse_embedding=model_esparso, # Habilita Híbrido
        url=url_qdrant,
        collection_name=col_data,
        retrieval_mode="hybrid",
        force_recreate=False
    )

print("\n✅ Ingestão Incremental Concluída!")