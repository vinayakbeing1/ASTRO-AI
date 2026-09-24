"""
LLM Chain Factory Module

This module provides utilities to create and configure LangChain chains with
structured output parsing and comprehensive logging capabilities.
"""

import json
import time
from typing import Any, Dict, TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from astro.models import PromptTemplate
from langchain.load import load
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages.system import SystemMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

# Initialize the OpenAI LLM with configured settings
openai_llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0)


class LLMLoggingHandler(BaseCallbackHandler):
    """
    Custom callback handler for logging LLM interactions.

    Tracks the start and end of chain executions, capturing prompts,
    responses, duration, and metadata for auditing and debugging purposes.
    """

    def __init__(self) -> None:
        """Initialize the handler with an empty runs dictionary."""
        self.runs = {}

    def on_chain_error(self, error: Exception, *, run_id: str, **kwargs) -> None:
        """
        Handle chain error by logging error information.

        Args:
            error: The exception that occurred
            run_id: Unique identifier for this run
            **kwargs: Additional keyword arguments
        """
        if run_id in self.runs:
            # Import here to avoid circular dependency
            from astro.models import LLMLog

            run_data = self.runs.pop(run_id)
            duration = time.perf_counter() - run_data["started_at"]

            LLMLog.objects.update_or_create(
                run_id=run_id,
                defaults={
                    "prompt": json.dumps(run_data["prompt"]),
                    "response": f"ERROR: {str(error)}",
                    "duration": duration,
                    "user": run_data["user"],
                    "chain_type": run_data["chain_type"],
                },
            )

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        parent_run_id: str,
        **kwargs,
    ) -> None:
        """
        Handle chain start event by capturing initial state.

        Args:
            serialized: Serialized chain data
            inputs: Input data for the chain
            parent_run_id: Unique identifier for this run
            **kwargs: Additional keyword arguments including metadata
        """
        prompt_template = load(serialized)
        if serialized and isinstance(prompt_template, ChatPromptTemplate):
            formatted_messages = prompt_template.format_messages(**inputs)
            metadata = kwargs.get("metadata", {})

            self.runs[parent_run_id] = {
                "started_at": time.perf_counter(),
                "prompt": [
                    {
                        "role": (
                            "system" if isinstance(prompt, SystemMessage) else "user"
                        ),
                        "content": prompt.content,
                    }
                    for prompt in formatted_messages
                ],
                "user": metadata.get("user"),
                "chain_type": metadata.get("chain_type"),
            }

    def on_chain_end(self, outputs: Dict[str, Any], *, run_id: str, **kwargs) -> None:
        """
        Handle chain end event by logging results to database.

        Args:
            outputs: Chain output data
            run_id: Unique identifier for this run
            **kwargs: Additional keyword arguments
        """
        if run_id not in self.runs or outputs is None:
            return

        # Import here to avoid circular dependency
        from astro.models import LLMLog

        run_data = self.runs.pop(run_id)
        duration = time.perf_counter() - run_data["started_at"]

        LLMLog.objects.update_or_create(
            run_id=run_id,
            defaults={
                "prompt": json.dumps(run_data["prompt"]),
                "response": outputs.model_dump(),
                "duration": duration,
                "user": run_data["user"],
                "chain_type": run_data["chain_type"],
            },
        )


def create_llm_chain(
    parser, prompt_template: "PromptTemplate", metadata: Dict[str, Any] = None
) -> Any:
    """
    Create a LangChain chain with structured output and logging.

    Args:
        parser: Pydantic model for structured output parsing
        prompt_template: Template containing system and user messages
        metadata: Optional metadata for logging (default: empty dict)

    Returns:
        Configured LangChain chain with logging callbacks

    Raises:
        ValueError: If prompt_template is missing required fields
        Exception: If chain creation fails
    """
    # Import here to avoid circular dependency
    from astro.models import PromptTemplate

    if metadata is None:
        metadata = {}

    # Validate prompt template
    if not prompt_template.system_message or not prompt_template.user_message:
        raise ValueError(
            f"Prompt template '{prompt_template.name}' missing required " "messages"
        )

    try:
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    prompt_template.system_message
                ),
                HumanMessagePromptTemplate.from_template(prompt_template.user_message),
            ]
        )
        if not parser:
            prompt_chain = prompt | openai_llm
        else:
            prompt_chain = prompt | openai_llm.with_structured_output(parser)

        return prompt_chain.with_config(
            callbacks=[LLMLoggingHandler()], metadata=metadata
        )
    except Exception as e:
        raise Exception(f"Failed to create LLM chain: {str(e)}") from e
