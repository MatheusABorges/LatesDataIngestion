# Lattes Data Ingestion Pipeline

Este repositório contém o pipeline de ETL (Extract, Transform, Load) responsável por processar currículos da Plataforma Lattes, gerar embeddings vetoriais e indexá-los no banco de dados Qdrant.

O projeto foi desenhado para funcionar de forma **desacoplada** (Standalone), ideal para ser executado como um *job* periódico (cron/batch), garantindo que a base de conhecimento esteja sempre atualizada sem impactar a performance da API principal.

##  Funcionalidades

- **Parser XML :** Leitura da estrutura complexa dos XMLs do Lattes (Dados Gerais, Formação, Produção Bibliográfica, Projetos).
- **Chunking Semântico:** Divisão dos textos para maximizar a precisão da busca vetorial.
- **Embeddings Locais:** Utiliza o modelo `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` rodando localmente (CPU ou GPU).
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

Este projeto utiliza modelos da biblioteca `SentenceTransformers` para converter texto em vetores.

### Comportamento Padrão
1.  **Primeira Execução:** O script verifica se o modelo definido no `.env` existe na pasta local (`modelos_locais`). Se não existir, ele fará o **download automático** do Hugging Face (aprox. 1.1GB).
2.  **Execuções Seguintes:** O sistema carrega o modelo diretamente do disco. **Não é necessário acesso à internet** para execuções subsequentes.

### Instalação Manual (Ambientes Offline)
Se o servidor de produção não tiver acesso à internet:
1.  Em uma máquina conectada, baixe o modelo: `git clone https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
2.  Copie a pasta baixada para dentro de `LatesDataIngestion/modelos_locais`.
3.  Configure `MODEL_CACHE_DIR=./modelos_locais` no arquivo `.env`.

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

```python main.py```