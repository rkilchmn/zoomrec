from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import os
import logging
from typing import Optional

class LLMChat:
    def __init__(self, model: str, api_url: str, api_key_env: str):
        """
        Initialize the OpenRouter chat model using LangChain.

        :param model: The model identifier (e.g., "meta-llama/llama-4-maverick")
        :param api_url: The API base URL for the provider (e.g., "https://openrouter.ai/api/v1")
        :param api_key_env: Environment variable name that stores the API key
        """
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(f"API key environment variable {api_key_env} not set")
        
        self.chat = ChatOpenAI(
            openai_api_key=api_key,  # This was missing and is required
            openai_api_base=api_url,
            model=model,
            temperature=0  # We want deterministic responses for timezone mapping
        )

    def ask(self, prompt: str) -> Optional[str]:
        """
        Send a prompt to the LLM and return its response.

        :param prompt: The user's message.
        :return: The LLM's reply as a string or None if an error occurs.
        """
        try:
            messages = [HumanMessage(content=prompt)]
            response = self.chat.invoke(messages)
            return response.content.strip()
        except Exception as e:
            logging.error(f"Error in LLM chat: {str(e)}", exc_info=True)
            return None
