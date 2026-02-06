"""
LLM Client for AI Operations Assistant.
Provides async Gemini client with structured JSON output and retry logic.
"""

import json
import re
from typing import Any, Dict, Optional, Type, TypeVar
from functools import lru_cache
import google.generativeai as genai
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Async client for Google Gemini with structured output support."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model or settings.gemini_model
        
        # Configure the SDK
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
        
        # Track usage
        self.total_tokens_used = 0
        self.request_count = 0
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response, handling markdown code blocks."""
        # Try to find JSON in code blocks first
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Try to parse the entire response as JSON
            json_str = text.strip()
        
        # Remove any leading/trailing whitespace and parse
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try to find JSON object pattern
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Could not extract valid JSON from response: {text[:500]}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Generate text response from the LLM."""
        self.request_count += 1
        
        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        try:
            # Use synchronous API (Gemini's async is still evolving)
            response = self.model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
            )
            
            result = response.text
            logger.info(f"LLM generated response", extra={
                "model": self.model_name,
                "prompt_length": len(full_prompt),
                "response_length": len(result)
            })
            
            return result
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def generate_structured(
        self,
        prompt: str,
        output_schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3  # Lower temperature for structured output
    ) -> T:
        """Generate structured output conforming to a Pydantic schema."""
        # Add schema hint to prompt
        schema_hint = f"\n\nRespond with valid JSON matching this schema:\n{output_schema.model_json_schema()}"
        enhanced_prompt = prompt + schema_hint
        
        response_text = await self.generate(
            enhanced_prompt,
            system_prompt=system_prompt,
            temperature=temperature
        )
        
        # Parse JSON and validate with Pydantic
        try:
            json_data = self._extract_json(response_text)
            result = output_schema.model_validate(json_data)
            return result
        except Exception as e:
            logger.error(f"Failed to parse structured output: {e}", extra={
                "response_preview": response_text[:500]
            })
            raise ValueError(f"Failed to parse LLM response as {output_schema.__name__}: {e}")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "request_count": self.request_count,
            "model": self.model_name
        }


@lru_cache()
def get_llm_client() -> LLMClient:
    """Get cached LLM client instance."""
    return LLMClient()
