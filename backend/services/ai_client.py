"""
AI Client Abstraction Layer for MedAdvice v4

Supports dual-environment deployment:
- Anthropic: Direct API access for local development
- Bedrock: AWS Bedrock for production deployment

Usage:
    from backend.services.ai_client import get_ai_client
    from backend.config import settings
    
    client = get_ai_client(settings)
    response = client.create_message(
        messages=[{"role": "user", "content": "Hello"}],
        system="You are a helpful assistant",
        max_tokens=1024
    )
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import time
import random
import logging

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    """Base exception for AI client errors"""
    pass


class AIClientResponse:
    """Standardized response object from AI clients"""
    
    def __init__(
        self,
        id: str,
        content: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        stop_reason: str
    ):
        self.id = id
        self.content = content
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.stop_reason = stop_reason
    
    @property
    def usage(self) -> Dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "model": self.model,
            "usage": self.usage,
            "stop_reason": self.stop_reason
        }


class AIClient(ABC):
    """Abstract base class for AI providers"""
    
    @abstractmethod
    def create_message(
        self,
        messages: List[Dict[str, str]],
        system: str,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> AIClientResponse:
        """
        Send messages and get a response from the AI model.
        
        Args:
            messages: List of message dicts with "role" and "content" keys
            system: System prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 - 1.0)
            
        Returns:
            AIClientResponse with standardized response data
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging"""
        pass


class AnthropicClient(AIClient):
    """Client for direct Anthropic API access (local development)"""
    
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise AIClientError("Anthropic API key is required")
        
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)
        self.model = model
        logger.info(f"Initialized Anthropic client with model: {model}")
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    def create_message(
        self,
        messages: List[Dict[str, str]],
        system: str,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> AIClientResponse:
        """Create a message using Anthropic's API with retry logic"""
        from anthropic import APIStatusError
        
        max_retries = 3
        retry_delay = 1.0
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=messages
                )
                
                return AIClientResponse(
                    id=response.id,
                    content=response.content[0].text,
                    model=response.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    stop_reason=response.stop_reason
                )
                
            except APIStatusError as e:
                last_error = e
                # Retry on transient errors (529, 503, 500)
                if e.status_code in (529, 503, 500):
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(
                            f"Anthropic API error {e.status_code}, "
                            f"retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                raise AIClientError(f"Anthropic API error: {e}") from e
        
        raise AIClientError(f"Anthropic API error after {max_retries} retries: {last_error}")


class BedrockClient(AIClient):
    """Client for AWS Bedrock (production deployment)"""
    
    def __init__(self, region: str, model_id: str):
        import boto3
        from botocore.config import Config
        
        # Configure retry behavior
        config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            }
        )
        
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=config
        )
        self.model_id = model_id
        self.region = region
        logger.info(f"Initialized Bedrock client with model: {model_id} in region: {region}")
    
    @property
    def provider_name(self) -> str:
        return "bedrock"
    
    def create_message(
        self,
        messages: List[Dict[str, str]],
        system: str,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> AIClientResponse:
        """Create a message using AWS Bedrock's API"""
        from botocore.exceptions import ClientError
        
        # Build request body for Claude on Bedrock
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": messages
        })
        
        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            
            result = json.loads(response["body"].read())
            
            return AIClientResponse(
                id=result.get("id", f"bedrock-{int(time.time())}"),
                content=result["content"][0]["text"],
                model=self.model_id,
                input_tokens=result["usage"]["input_tokens"],
                output_tokens=result["usage"]["output_tokens"],
                stop_reason=result.get("stop_reason", "end_turn")
            )
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise AIClientError(
                f"Bedrock API error ({error_code}): {error_message}"
            ) from e
        except json.JSONDecodeError as e:
            raise AIClientError(f"Failed to parse Bedrock response: {e}") from e
        except KeyError as e:
            raise AIClientError(f"Unexpected Bedrock response format: missing {e}") from e


def get_ai_client(settings) -> AIClient:
    """
    Factory function to get the appropriate AI client based on settings.
    
    Args:
        settings: Settings object with ai_provider and related configuration
        
    Returns:
        AIClient instance (AnthropicClient or BedrockClient)
        
    Raises:
        AIClientError: If provider is unknown or configuration is invalid
    """
    provider = settings.ai_provider.lower()
    
    if provider == "bedrock":
        logger.info(f"Creating Bedrock client for region: {settings.aws_region}")
        return BedrockClient(
            region=settings.aws_region,
            model_id=settings.bedrock_model_id
        )
    elif provider == "anthropic":
        logger.info("Creating Anthropic client")
        return AnthropicClient(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model
        )
    else:
        raise AIClientError(
            f"Unknown AI provider: {provider}. "
            f"Valid options are 'anthropic' or 'bedrock'"
        )
