"""
Single place that decides which chat model backs the LangGraph agent nodes.

Embeddings (RAG) stay on local Ollama regardless of this setting — retrieval
doesn't need frontier-model reasoning, and keeping it local means the whole
knowledge base is never sent anywhere. This factory only controls the model
used for tool-calling / reasoning steps (repro, triage, code fix), which is
where a stronger hosted model like Gemini Flash meaningfully helps.
"""
from langchain_core.language_models import BaseChatModel

from app.config import settings


def get_chat_llm(temperature: float = 0) -> BaseChatModel:
    """Returns the configured chat model, bindable with `.bind_tools(...)`."""
    if settings.LLM_PROVIDER == "gemini":
        if not settings.GOOGLE_API_KEY:
            raise RuntimeError("LLM_PROVIDER=gemini requires GOOGLE_API_KEY to be set.")

        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=temperature,
        )

    if settings.LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=settings.OLLAMA_MODEL, temperature=temperature)

    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r} (expected 'ollama' or 'gemini')")
