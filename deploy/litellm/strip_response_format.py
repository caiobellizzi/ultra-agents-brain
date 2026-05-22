"""LiteLLM pre-call hook: strip response_format from local-model requests when tools are present.

Background: LM Studio's llama.cpp backend cannot combine grammar-based structured output
(response_format=json_schema) with tool-calling grammar (lazy grammar). This raises
'Cannot combine structured output constraints with lazy grammar' (HTTP 400).

This hook drops response_format from local-model requests that also carry tools.
Tool calls still work; the caller just loses the JSON-schema validation on the response.
"""
from typing import Literal, Optional

from litellm.integrations.custom_logger import CustomLogger

LOCAL_MODELS = {"orchestrator", "default-worker", "cheap-worker", "private-worker"}


class StripResponseFormatForLocalModels(CustomLogger):
    async def async_pre_call_hook(
        self,
        user_api_key_dict,
        cache,
        data: dict,
        call_type,
    ) -> Optional[dict]:
        model = data.get("model", "")
        if model in LOCAL_MODELS and data.get("tools") and data.get("response_format"):
            data.pop("response_format", None)
        return data


proxy_handler_instance = StripResponseFormatForLocalModels()
