"""
LLM Executor using LiteLLM
"""

from typing import Dict, Any, Optional
from apflow.core.base import BaseTask
from apflow.core.execution.errors import ValidationError
from apflow.logger import get_logger

logger = get_logger(__name__)

# Try to import litellm, mark availability for tests and runtime checks
try:
    import litellm

    LITELLM_AVAILABLE = True
except ImportError:
    litellm = None  # type: ignore
    LITELLM_AVAILABLE = False
    logger.warning(
        "litellm is not installed. LLM executor will not be available. "
        "Install it with: pip install apflow[llm]"
    )

# Only register if litellm is available (prevents registration failure when dependency is missing)
if LITELLM_AVAILABLE:
    from apflow.core.extensions.decorators import executor_register
else:
    # No-op decorator when litellm is not available
    def executor_register(*args, **kwargs):
        def decorator(cls):
            return cls

        return decorator


@executor_register()
class LLMExecutor(BaseTask):
    """
    Executor for interacting with LLMs via LiteLLM.

    Supports:
    - Text generation (Chat Completion)
    - Streaming (SSE compatible output structure)
    - Multiple providers (OpenAI, Anthropic, Gemini, etc.)

    Example usage in task schemas:
    {
        "schemas": {
            "method": "llm_executor"
        },
        "params": {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1000
        },
        "inputs": {
            "messages": [{"role": "user", "content": "Hello"}]
        }
    }
    """

    id = "llm_executor"
    name = "LLM Executor"
    description = "Execute LLM requests using LiteLLM (supports 100+ models)"
    tags = ["llm", "ai", "completion", "chat", "litellm"]
    examples = ["Generate text using GPT-4", "Chat with Claude", "Summarize text"]

    cancelable: bool = True

    @property
    def type(self) -> str:
        return "llm"

    def __init__(
        self,
        name: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        stream: Optional[bool] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ):
        """
        Initialize LLMExecutor

        Args:
            name: Executor name
            inputs: Input parameters (runtime business data)
            model: LLM model name (config - stored in params)
            api_key: API key (config)
            stream: Whether to stream (config)
            temperature: Temperature setting (config)
            max_tokens: Max tokens (config)
            **kwargs: Additional config
        """
        super().__init__(inputs=inputs, **kwargs)

        # Store config in params-like attributes (will be set by TaskManager from task.params)
        self._model = model
        self._api_key = api_key
        self._stream = stream
        self._temperature = temperature
        self._max_tokens = max_tokens

    id = "llm_executor"
    name = "LLM Executor"
    description = "Execute LLM requests using LiteLLM (supports 100+ models)"
    tags = ["llm", "ai", "completion", "chat", "litellm"]
    examples = ["Generate text using GPT-4", "Chat with Claude", "Summarize text"]

    cancelable: bool = True

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute LLM completion

        Args:
            inputs: Business input data containing:
                messages (List[Dict]): Chat messages (required)

        Returns:
            Dict containing only the LLM response content
        """
        # Get messages from inputs (business data)
        messages = inputs.get("messages")
        if not messages:
            raise ValidationError(f"[{self.id}] messages is required in inputs")

        # Get config from params (set during initialization)
        model = self._model
        if not model:
            model = inputs.get("model")
        if not model:
            raise ValidationError(f"[{self.id}] model is required in params or inputs")

        api_key = self._api_key
        stream = self._stream if self._stream is not None else False

        # Check for streaming in inputs or context metadata
        if not stream:
            stream = inputs.get("stream", False)
        if (
            not stream
            and hasattr(self, "context")
            and self.context
            and hasattr(self.context, "metadata")
        ):
            stream = self.context.metadata.get("stream", False)

        temperature = self._temperature
        max_tokens = self._max_tokens

        # Get LLM API key if not provided
        if not api_key:
            from apflow.core.utils.llm_key_context import get_llm_key
            from apflow.core.utils.llm_key_injector import detect_provider_from_model

            user_id = self.user_id or inputs.get("user_id")
            provider = detect_provider_from_model(model)
            api_key = get_llm_key(user_id=user_id, provider=provider, context="auto")
            if api_key:
                logger.debug(f"Retrieved LLM key for user {user_id}, provider {provider}")

        # Prepare kwargs
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if temperature is not None:
            completion_kwargs["temperature"] = temperature
        if max_tokens is not None:
            completion_kwargs["max_tokens"] = max_tokens

        logger.info(f"Executing LLM request: model={model}, stream={stream}")

        response = await litellm.acompletion(**completion_kwargs)

        if stream:
            # For streaming, return the generator wrapped appropriately
            return {
                "success": True,
                "is_stream": True,
                "stream": response,
                "usage": None,  # Usage not available during streaming
                "model": completion_kwargs.get("model"),
            }

        # Extract content (pure business result)
        result_dict = response.model_dump() if hasattr(response, "model_dump") else dict(response)
        content = None
        if "choices" in result_dict and len(result_dict["choices"]) > 0:
            content = result_dict["choices"][0].get("message", {}).get("content")

        return {
            "success": True,
            "content": content,
            "is_stream": False,
            "usage": result_dict.get("usage"),
            "model": result_dict.get("model"),
        }

    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo LLM response"""
        model = inputs.get("model", "demo-gpt")
        messages = inputs.get("messages", [])
        last_message = messages[-1]["content"] if messages else "Hello"

        demo_content = f"Attributes of {model}: This is a simulated response to '{last_message}'."

        return {
            "success": True,
            "content": demo_content,
            "is_stream": False,
            "usage": None,
            "model": model,
        }

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Chat messages like [{'role': 'user', 'content': '...'}]",
                },
            },
            "required": ["messages"],
        }

    def get_output_schema(self) -> Dict[str, Any]:
        """
        Return the output result schema for this executor.
        """
        return {
            "type": "object",
            "properties": {
                "success": {
                    "type": "boolean",
                    "description": "Whether the LLM call was successful",
                },
                "content": {"type": "string", "description": "LLM generated response content"},
                "is_stream": {"type": "boolean", "description": "Whether the response is a stream"},
                "stream": {"description": "Stream generator (only present when is_stream is True)"},
                "usage": {"type": "object", "description": "Token usage information"},
                "model": {"type": "string", "description": "Model used for the completion"},
            },
            "required": ["success", "is_stream"],
        }
