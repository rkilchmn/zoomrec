from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import os
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential

class LLMChat:
    def __init__(self, model: str, api_url: str, api_key_env: str, max_retries: int = 3):
        """
        Initialize the OpenRouter chat model using LangChain.

        :param model: The model identifier (e.g., "meta-llama/llama-4-maverick")
        :param api_url: The API base URL for the provider (e.g., "https://openrouter.ai/api/v1")
        :param api_key_env: Environment variable name that stores the API key
        :param max_retries: Maximum number of retry attempts for failed requests
        """
        self.api_key = os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(f"API key environment variable {api_key_env} not set")
        
        self.model = model
        self.api_url = api_url
        self.max_retries = max_retries
        
        self._init_chat()
    
    def _init_chat(self):
        """Initialize the chat client with current settings."""
        self.chat = ChatOpenAI(
            openai_api_key=self.api_key,
            openai_api_base=self.api_url,
            model=self.model,
            temperature=0,  # We want deterministic responses for timezone mapping
            max_retries=self.max_retries
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _invoke_with_retry(self, messages):
        """Invoke the chat with retry logic using tenacity."""
        return self.chat.invoke(messages)

    def ask(self, prompt: str) -> Optional[str]:
        """
        Send a prompt to the LLM and return its response.
        Retries are handled by the @retry decorator on _invoke_with_retry.

        :param prompt: The user's message.
        :return: The LLM's reply as a string or None if all retries are exhausted.
        """
        try:
            messages = [HumanMessage(content=prompt)]
            response = self._invoke_with_retry(messages)
            return response.content.strip()
        except Exception as e:
            logging.error(f"Failed to get response after retries: {str(e)}", exc_info=True)
            return None
