from typing import List
from langchain_core.embeddings import Embeddings
from openai import OpenAI


class LMStudioEmbeddings(Embeddings):
    def __init__(
        self,
        model: str = "text-embedding-embeddinggemma-300m",
        base_url: str = "http://host.docker.internal:1234/v1",
        api_key: str = "lm-studio",
    ):
        self.model = model
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            text = text.replace("\n", " ")
            response = self._client.embeddings.create(input=[text], model=self.model)
            embeddings.append(response.data[0].embedding)
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        text = text.replace("\n", " ")
        return self._client.embeddings.create(input=[text], model=self.model).data[0].embedding
