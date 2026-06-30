"""Configurable LLM and embedding backends."""

from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from interview_prep.config import Settings


def create_chat_model(settings: Settings) -> BaseChatModel:
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
        )
   # if provider == "openai":
    #    from langchain_openai import ChatOpenAI

     #   return ChatOpenAI(
      #      model=settings.llm_model,
       #     temperature=settings.llm_temperature,
       # )
    raise ValueError(f"Unsupported LLM provider: {provider}")


def create_embeddings(settings: Settings) -> Embeddings:
    provider = settings.embeddings_provider.lower()
    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=settings.embeddings_model,
            base_url=settings.embeddings_base_url,
        )
    #if provider == "openai":
     #   from langchain_openai import OpenAIEmbeddings

     #   return OpenAIEmbeddings(model=settings.embeddings_model)
    raise ValueError(f"Unsupported embeddings provider: {provider}")
