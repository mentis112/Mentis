from app.adapters.ai.base import BaseAIProvider
from app.adapters.ai.deepseek_provider import DeepSeekProvider
from app.adapters.ai.gemini_provider import GeminiProvider
from app.adapters.ai.groq_provider import GroqProvider
from app.adapters.ai.ollama_provider import OllamaProvider
from app.adapters.ai.openai_provider import OpenAIProvider
from app.models.enums import ProviderName


class ProviderAdapterFactory:
    @staticmethod
    def create(provider_name: ProviderName) -> BaseAIProvider:
        if provider_name == ProviderName.OPENAI:
            return OpenAIProvider()
        if provider_name == ProviderName.GEMINI:
            return GeminiProvider()
        if provider_name == ProviderName.DEEPSEEK:
            return DeepSeekProvider()
        if provider_name == ProviderName.GROQ:
            return GroqProvider()
        if provider_name == ProviderName.OLLAMA:
            return OllamaProvider()
        raise ValueError(f"Unsupported provider: {provider_name}")
