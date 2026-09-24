"""
LLM service package for AstroAI.

This package contains modules for managing Large Language Model interactions,
including chain creation, logging, and structured output parsing.
"""

from .chain_factory import create_llm_chain, LLMLoggingHandler

__all__ = ["create_llm_chain", "LLMLoggingHandler"]
