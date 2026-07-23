# Lattes Data Ingestion Pipeline

Este repositório contém o pipeline de ETL (Extract, Transform, Load) responsável por processar currículos da Plataforma Lattes, gerar embeddings vetoriais e indexá-los no banco de dados Qdrant.

O projeto foi desenhado para funcionar de forma **desacoplada** (Standalone), ideal para ser executado como um *job* periódico (cron/batch), garantindo que a base de conhecimento esteja sempre atualizada sem impactar a performance da API principal.

##  Funcionalidades

- **Parser XML :** Leitura da estrutura complexa dos XMLs do Lattes (Dados Gerais, Formação, Produção Bibliográfica, Projetos).
- **Chunking Semântico:** Divisão dos textos para maximizar a precisão da busca vetorial.
- **Embeddings Locais:** Modelo configurável via `.env` (padrão: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`) rodando localmente (CPU ou GPU) — ver "Sobre o Modelo de Embeddings" abaixo.
- **Integração com Qdrant:** Indexação vetorial de alta performance.

---

## Pré-requisitos

Antes de começar, certifique-se de que seu ambiente possui:

1.  **Python 3.10** ou superior.
2.  **Docker & Docker Compose** (Necessário para rodar o banco Qdrant).
3.  **Git**.
4.  *(Opcional)* **Drivers NVIDIA** configurados (caso deseje processamento acelerado por GPU).

---

## Sobre o Modelo de Embeddings

Este projeto utiliza modelos da biblioteca `SentenceTransformers` para converter texto em vetores, configurado via `EMBEDDING_MODEL_NAME` no `.env`.

**Esse modelo precisa ser exatamente o mesmo configurado no agente** (`EMBEDDING__MODEL_NAME` no `.env` do `LattesRagAgent`). Um vetor de consulta gerado por um modelo e comparado contra vetores de documento gerados por outro produz busca semântica degradada — sem nenhum erro visível, os dois lados simplesmente "falam línguas diferentes". Não há checagem automática entre os dois repositórios; é responsabilidade de quem configura o `.env` de cada um manter os dois em sincronia.

### Prefixo/prompt do modelo (assimetria consulta vs. documento)

O padrão atual, `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`, é um modelo **simétrico** — não precisa de prefixo nem prompt nomeado, `EMBEDDING_PREFIX`/`EMBEDDING_PROMPT_NAME` ficam vazios.

O código já tem suporte pronto para modelos **assimétricos**, caso troquem o padrão no futuro: alguns modelos esperam um prefixo literal colado no início do texto antes de embedar, diferente para cada papel — ex: a família `intfloat/multilingual-e5-*` usa `"passage: "` para documentos (o que este script sempre embeda), configurado em `EMBEDDING_PREFIX`; o lado consulta (`"query: "`) é responsabilidade do agente, configurado lá em `EMBEDDING__QUERY_PREFIX`. Sem esse prefixo o modelo roda normalmente, só que com qualidade sensivelmente pior — não há erro que avise disso. Alguns outros modelos (ex: EmbeddingGemma) usam em vez disso o mecanismo de "prompt nomeado" do próprio `sentence-transformers` — para esses, use `EMBEDDING_PROMPT_NAME` (ex: `retrieval_document`) em vez do prefixo literal.

**Já testamos `intfloat/multilingual-e5-base` e revertemos** — ranqueia melhor que o padrão atual no benchmark [MTEB-BR](https://arxiv.org/abs/2607.04581) (Português), mas a troca combinada com um novo reranker (ver README do `LattesRagAgent`, seção "Modelo de Reranking") causou citações de pesquisadores não-relacionados nas respostas. Revertido por segurança sem isolar qual dos dois era a causa raiz. Candidato a reavaliar no futuro, testando um de cada vez.

### Comportamento Padrão (download automático)

`EMBEDDING_MODEL_NAME` aceita um **repo ID do Hugging Face** (ex: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`) — nesse caso, a primeira execução baixa e cacheia o modelo automaticamente em `EMBEDDING_CACHE_FOLDER` (padrão: `./modelos_locais_cache`), sem nenhum passo manual. Execuções seguintes carregam do cache local, sem precisar de internet novamente.

### Instalação Manual (Ambientes Offline)

Se o servidor de produção não tiver acesso à internet, `EMBEDDING_MODEL_NAME` também aceita um **caminho local** já baixado manualmente:
1.  Em uma máquina conectada, baixe o modelo: `git clone https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
2.  Copie a pasta baixada para dentro de `LatesDataIngestion/modelos_locais/` (ex: `modelos_locais/mpnet-v2`).
3.  Configure `EMBEDDING_MODEL_NAME=./modelos_locais/mpnet-v2` no `.env` (caminho local — o script detecta que já existe e não tenta baixar).

---

## Instalação e Configuração

Siga os passos abaixo para preparar o ambiente de desenvolvimento.

### 1. Clonar o Repositório

```bash
git clone https://github.com/seu-usuario/LatesDataIngestion.git
cd LatesDataIngestion
```

### 2. Criar e Ativar Ambiente Virtual

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Configuração (.env)
O sistema é configurável via variáveis de ambiente.
Crie um arquivo chammado **.env** na raiz do projeto, copie o conteúdo do arquivo .env_template e ajuste as configurações conforme seu ambiente.

## Como executar

### Passo 1: Executar Banco de Dados(Qdrant):
Caso não possua o Qdrant rodando, é possível utilizar o comando abaixo para criar uma instância local Docker rapidamente:

```bash
docker run -d \
  --name qdrant_lattes \
  -p 6333:6333 \
  -v $(pwd)/qdrant_data:/qdrant/storage \
  qdrant/qdrant
```

### Passo 2: Preparar os Dados:
Coloque os arquivos XML exportados do Lattes dentro da pasta configurada no arquivo .env

### Passo 3: Rodar a Ingestão:

```python main_ingestion.py```