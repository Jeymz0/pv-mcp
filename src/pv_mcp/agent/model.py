"""Chat model construction. The graph depends on the LangChain chat interface."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from pv_mcp.agent.settings import AgentSettings


def build_chat_model(settings: AgentSettings) -> BaseChatModel:
    """Build the configured chat model.

    Groq reads ``GROQ_API_KEY`` from the environment. Other providers keep
    their own credential names. The graph never imports a provider class.
    """

    if settings.pv_agent_model_provider == "groq" and settings.groq_api_key is None:
        raise ValueError("GROQ_API_KEY is required to draft a summary.")
    return init_chat_model(
        settings.pv_agent_model,
        model_provider=settings.pv_agent_model_provider,
    )
