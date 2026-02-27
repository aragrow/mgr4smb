"""
LLM Service for interfacing with Google Gemini and other LLM providers

Handles prompt formatting, API calls, and response parsing
"""

import json
import logging
from typing import Dict, Any, Optional
from google import genai
from src.config.settings import get_settings
from src.models.agent_prompt import AgentPrompt

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with LLM providers"""

    def __init__(self):
        """Initialize LLM service with API credentials"""
        settings = get_settings()

        # Initialize Google Gemini client
        self.client = genai.Client(api_key=settings.google_api_key)

    def format_prompt(
        self,
        agent_prompt: AgentPrompt,
        variables: Dict[str, Any]
    ) -> tuple[str, str]:
        """
        Format system and user prompts with provided variables

        Args:
            agent_prompt: Agent prompt template from database
            variables: Dictionary of variables to substitute

        Returns:
            Tuple of (system_prompt, formatted_user_prompt)
        """
        # Format user prompt with variables
        user_prompt = agent_prompt.user_prompt_template.format(**variables)

        return agent_prompt.system_prompt, user_prompt

    async def classify_intent(
        self,
        agent_prompt: AgentPrompt,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to classify intent based on agent prompt

        Args:
            agent_prompt: Agent prompt configuration
            variables: Variables to fill in the user prompt template

        Returns:
            Parsed JSON response from LLM

        Raises:
            ValueError: If LLM returns invalid JSON
            Exception: If API call fails
        """
        try:
            # Format prompts
            system_prompt, user_prompt = self.format_prompt(agent_prompt, variables)

            # Combine system and user prompts
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            # Add explicit JSON instruction to prompt
            json_instruction = "\n\nIMPORTANT: Return ONLY the JSON object with no additional text, explanations, or markdown formatting."
            full_prompt_with_json = full_prompt + json_instruction

            logger.info(f"Calling LLM with model={agent_prompt.model}, temp={agent_prompt.temperature}")

            # Generate response using new API
            response = self.client.models.generate_content(
                model=agent_prompt.model,
                contents=full_prompt_with_json,
                config={
                    'temperature': agent_prompt.temperature,
                    'max_output_tokens': agent_prompt.max_tokens,
                }
            )

            # Extract text
            if not response.text:
                logger.error(f"LLM returned empty response. Full response: {response}")
                logger.error(f"Prompt was: {full_prompt[:500]}...")
                raise ValueError("LLM returned empty response")

            response_text = response.text.strip()

            # Extract token usage if available
            token_count = None
            if hasattr(response, 'usage_metadata'):
                token_count = {
                    'prompt_tokens': getattr(response.usage_metadata, 'prompt_token_count', None),
                    'completion_tokens': getattr(response.usage_metadata, 'candidates_token_count', None),
                    'total_tokens': getattr(response.usage_metadata, 'total_token_count', None)
                }
                logger.info(f"Token usage: {token_count}")

            logger.info(f"LLM Response (first 200 chars): {response_text[:200]}")

            # Parse JSON response
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith("```"):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove ```

            response_text = response_text.strip()

            # Parse JSON
            try:
                parsed_response = json.loads(response_text)
            except json.JSONDecodeError as e:
                # Log the problematic response for debugging
                logger.error(f"JSON parsing failed: {e}")
                logger.error(f"Problematic JSON (first 500 chars): {response_text[:500]}")
                logger.error(f"Full JSON response: {response_text}")

                # Attempt multiple repair strategies
                import re

                # Strategy 1: Try to extract and fix truncated JSON
                # The response might be incomplete, so we need to handle that
                repaired = response_text.strip()

                # If it starts with { but doesn't end with }, it's truncated
                if repaired.startswith('{') and not repaired.endswith('}'):
                    logger.info("Detected truncated JSON response")
                    logger.info(f"Truncated content: {repaired}")

                    # Strategy: Remove everything after the last complete key-value pair
                    # Find the position of the last comma that's not inside a string
                    last_valid_comma = -1
                    in_string = False
                    for i, char in enumerate(repaired):
                        if char == '"' and (i == 0 or repaired[i-1] != '\\'):
                            in_string = not in_string
                        elif char == ',' and not in_string:
                            last_valid_comma = i

                    # If we found a comma, truncate to there
                    if last_valid_comma > 0:
                        logger.info(f"Truncating to last valid comma at position {last_valid_comma}")
                        repaired = repaired[:last_valid_comma].rstrip()
                    else:
                        # No comma found, try to salvage what we have
                        # Check if there's an unterminated string
                        quotes = repaired.count('"') - repaired.count('\\"')
                        if quotes % 2 != 0:
                            logger.info("Fixing unterminated string by removing incomplete part...")
                            # Find the last opening quote and remove everything after it
                            last_quote = repaired.rfind('"')
                            if last_quote > 0:
                                # Check if this quote is the start of a key (preceded by comma or brace)
                                prev_char_idx = last_quote - 1
                                while prev_char_idx >= 0 and repaired[prev_char_idx] in ' \n\t':
                                    prev_char_idx -= 1
                                if prev_char_idx >= 0 and repaired[prev_char_idx] in ',{':
                                    # Remove the incomplete key
                                    repaired = repaired[:last_quote].rstrip()
                                    if repaired.endswith(','):
                                        repaired = repaired[:-1].rstrip()

                    # Count open and close braces
                    open_braces = repaired.count('{')
                    close_braces = repaired.count('}')

                    # Add missing closing braces
                    missing_braces = open_braces - close_braces
                    if missing_braces > 0:
                        logger.info(f"Adding {missing_braces} missing closing brace(s)...")
                        repaired += '}' * missing_braces

                    logger.info(f"Repaired JSON: {repaired}")

                # Strategy 2: Extract JSON object if embedded in text
                json_match = re.search(r'\{.*\}', repaired, re.DOTALL)
                if json_match:
                    repaired = json_match.group()

                # Strategy 3: Replace single quotes with double quotes
                repaired = repaired.replace("'", '"')

                # Try parsing the repaired JSON
                try:
                    logger.info("Attempting to parse repaired JSON...")
                    parsed_response = json.loads(repaired)
                    logger.info("✓ Successfully parsed repaired JSON!")
                except json.JSONDecodeError as repair_error:
                    logger.error(f"Repaired JSON still invalid: {repair_error}")
                    logger.error(f"Repaired JSON: {repaired[:500]}")

                    # Strategy 4: Try to fix trailing commas
                    repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)
                    try:
                        logger.info("Attempting to parse JSON after removing trailing commas...")
                        parsed_response = json.loads(repaired)
                        logger.info("✓ Successfully parsed after comma fix!")
                    except json.JSONDecodeError:
                        logger.error(f"All repair strategies failed")
                        logger.error(f"Original error: {e}")
                        logger.error(f"Full prompt was: {full_prompt[:500]}...")
                        raise ValueError(f"LLM returned invalid JSON: {e}")

            logger.info(f"Successfully classified intent: {parsed_response}")

            # Add token usage to response if available
            if token_count:
                parsed_response['_token_usage'] = token_count

            return parsed_response

        except Exception as e:
            logger.error(f"LLM classification failed: {e}", exc_info=True)
            raise

    async def generate_text(
        self,
        prompt: str,
        model_name: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        Generate text using LLM (for general purpose generation)

        Args:
            prompt: The prompt to send to the LLM
            model_name: Model to use
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        try:
            if model_name is None:
                model_name = get_settings().google_model
            logger.info(f"Generating text with model={model_name}, temp={temperature}, max_tokens={max_tokens}")
            logger.debug(f"Prompt (first 500 chars): {prompt[:500]}")

            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    'temperature': temperature,
                    'max_output_tokens': max_tokens,
                }
            )

            # Check finish_reason for debugging
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = getattr(response.candidates[0], 'finish_reason', None)
                if finish_reason and finish_reason != 'STOP':
                    logger.warning(f"LLM finished with reason: {finish_reason} (not STOP)")

            result = response.text.strip()
            logger.info(f"Generated {len(result)} characters")

            # Log token usage if available
            if hasattr(response, 'usage_metadata'):
                token_usage = {
                    'prompt_tokens': getattr(response.usage_metadata, 'prompt_token_count', None),
                    'completion_tokens': getattr(response.usage_metadata, 'candidates_token_count', None),
                    'total_tokens': getattr(response.usage_metadata, 'total_token_count', None)
                }
                logger.info(f"Token usage: {token_usage}")

            logger.debug(f"Response: {result}")

            return result

        except Exception as e:
            logger.error(f"Text generation failed: {e}", exc_info=True)
            raise
