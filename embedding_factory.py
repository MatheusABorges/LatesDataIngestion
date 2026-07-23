import os
from typing import List
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import FastEmbedSparse


class PrefixedHuggingFaceEmbeddings(HuggingFaceEmbeddings):
    prefix: str = ""

    def embed_query(self, text: str) -> List[float]:
        return super().embed_query(self.prefix + text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return super().embed_documents([self.prefix + t for t in texts])


class EmbeddingHandler:
    def __init__(self, provider: str, model_name: str, api_key: str = None, is_ingestion: bool = True, device: str = "cpu", prompt_name: str = None, prefix: str = None, cache_folder: str = "./modelos_locais_cache"):
        """
        Inicializa o handler para vetores DENSOS.
        """
        self.provider = provider.lower().strip()
        self.model_name = model_name.strip()
        self.api_key = api_key
        self.is_ingestion = is_ingestion
        self.device = device
        self.cache_folder = cache_folder
        self.prompt_name = prompt_name  # ex: "retrieval_document" (EmbeddingGemma)
        self.prefix = prefix or ""  # ex: "passage: " (intfloat/multilingual-e5-*)
        
        self._model_instance = self._create_model()
        self._dimension = self._calculate_dimension()
        
        print(f"Embedding Handler (Denso) pronto: {self.provider} | Dimensão: {self._dimension}")

    @staticmethod
    def get_sparse_model():
        """
        Retorna o modelo de vetores ESPARSOS (BM25/SPLADE) para busca híbrida.
        """
        print("Carregando modelo Esparso (BM25)...")
        return FastEmbedSparse(model_name="Qdrant/bm25")

    @property
    def model(self) -> Embeddings:
        return self._model_instance

    @property
    def dimension(self) -> int:
        return self._dimension

    def _create_model(self) -> Embeddings:
        # --- HUGGING FACE LOCAL ---
        if self.provider == "huggingface_local":
            looks_like_local_path = self.model_name.startswith((".", "/", "~")) or "\\" in self.model_name
            if looks_like_local_path and not os.path.exists(self.model_name):
                print(f"Caminho '{self.model_name}' não existe. Esse modelo precisa ser baixado manualmente antes (ver README, seção 'Modelo de Embeddings').")
                raise FileNotFoundError(f"Modelo local não encontrado em '{self.model_name}'.")

            encode_kwargs = {}
            if self.prompt_name:
                encode_kwargs["prompt_name"] = self.prompt_name

            return PrefixedHuggingFaceEmbeddings(
                model_name=self.model_name,
                cache_folder=None if looks_like_local_path else self.cache_folder,
                model_kwargs={"device": self.device},
                encode_kwargs=encode_kwargs,
                prefix=self.prefix,
            )

        # --- GOOGLE ---
        elif self.provider == "google":
            if not self.api_key:
                raise ValueError("API Key é obrigatória para provider Google.")
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            task_type = "retrieval_document" if self.is_ingestion else "retrieval_query"
            return GoogleGenerativeAIEmbeddings(model=self.model_name, google_api_key=self.api_key, task_type=task_type)
            
        # --- OPENAI ---
        elif self.provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(model=self.model_name, api_key=self.api_key)

        else:
            raise ValueError(f"Provedor '{self.provider}' não suportado.")

    def _calculate_dimension(self) -> int:
        """Método interno que roda um teste real para saber o tamanho"""
        try:
            test_vector = self._model_instance.embed_query("teste de dimensão")
            return len(test_vector)
        except Exception as e:
            raise RuntimeError(f"Falha ao calcular dimensão do modelo: {e}")