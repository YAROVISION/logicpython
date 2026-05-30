import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

class LLMRotator:
    def __init__(self):
        # Load from current directory
        load_dotenv()
        load_dotenv(dotenv_path='.env.local', override=True)
        
        # Fallback to search in parent directories if keys are not loaded yet
        if not any(os.getenv(k) for k in ["GROQ_API_KEY", "CEREBRAS_API_KEY", "SAMBANOVA_API_KEY", "NVIDIA_API_KEY", "CLOUDFLARE_API_KEY", "OPENROUTERFORSKILLFORDIGEST"]):
            from dotenv import find_dotenv
            env_path = find_dotenv('.env')
            if env_path:
                load_dotenv(env_path)
            env_local_path = find_dotenv('.env.local')
            if env_local_path:
                load_dotenv(env_local_path, override=True)

        self.providers = [
            {
                "name": "groq",
                "base_url": "https://api.groq.com/openai/v1",
                "api_key": os.getenv("GROQ_API_KEY"),
                "model": "llama-3.3-70b-versatile"
            },
            {
                "name": "groq",
                "base_url": "https://api.groq.com/openai/v1",
                "api_key": os.getenv("GROQ_API_KEY"),
                "model": "llama-3.1-8b-instant"
            },
            {
                "name": "cerebras",
                "base_url": "https://api.cerebras.ai/v1",
                "api_key": os.getenv("CEREBRAS_API_KEY"),
                "model": "llama3.1-8b"
            },
            {
                "name": "cerebras",
                "base_url": "https://api.cerebras.ai/v1",
                "api_key": os.getenv("CEREBRAS_API_KEY"),
                "model": "qwen-3-235b-a22b-instruct-2507"
            },
            {
                "name": "cerebras",
                "base_url": "https://api.cerebras.ai/v1",
                "api_key": os.getenv("CEREBRAS_API_KEY"),
                "model": "zai-glm-4.7"
            },
            {
                "name": "sambanova",
                "base_url": "https://api.sambanova.ai/v1",
                "api_key": os.getenv("SAMBANOVA_API_KEY"),
                "model": "Meta-Llama-3.3-70B-Instruct"
            },
            {
                "name": "sambanova",
                "base_url": "https://api.sambanova.ai/v1",
                "api_key": os.getenv("SAMBANOVA_API_KEY"),
                "model": "DeepSeek-V3.1"
            },
            {
                "name": "sambanova",
                "base_url": "https://api.sambanova.ai/v1",
                "api_key": os.getenv("SAMBANOVA_API_KEY"),
                "model": "Llama-4-Maverick-17B-128E-Instruct"
            },
            {
                "name": "nvidia",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "api_key": os.getenv("NVIDIA_API_KEY"),
                "model": "qwen/qwen3-coder-480b-a35b-instruct"
            },
            {
                "name": "nvidia",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "api_key": os.getenv("NVIDIA_API_KEY"),
                "model": "mistralai/mistral-large-3-675b-instruct-2512"
            },
            {
                "name": "nvidia",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "api_key": os.getenv("NVIDIA_API_KEY"),
                "model": "google/gemma-3n-e4b-it"
            },
            {
                "name": "cloudflare",
                "base_url": f"https://api.cloudflare.com/client/v4/accounts/{os.getenv('CLOUDFLARE_ACCOUNT_ID')}/ai/v1",
                "api_key": os.getenv("CLOUDFLARE_API_KEY"),
                "model": "@cf/meta/llama-3.1-8b-instruct"
            },
            {
                "name": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": os.getenv("OPENROUTERFORSKILLFORDIGEST"),
                "model": "poolside/laguna-m.1:free"
            },
            {
                "name": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": os.getenv("OPENROUTERFORSKILLFORDIGEST"),
                "model": "google/gemma-4-26b-a4b-it:free"
            },
            {
                "name": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": os.getenv("OPENROUTERFORSKILLFORDIGEST"),
                "model": "qwen/qwen3-next-80b-a3b-instruct:free"
            },
            {
                "name": "ollama",
                "base_url": "http://localhost:11434/v1",
                "api_key": "ollama",
                "model": "qwen2.5-coder:14b"
            }
        ]
        
    def chat_completion(self, messages, response_format=None, preferred_provider=None):
        """
        Attempts to get a chat completion from providers in order.
        """
        # Filter out providers without API keys (except ollama)
        available_providers = [p for p in self.providers if p["api_key"] or p["name"] == "ollama"]
        print(f"🤖 [Rotator] Active providers in this run: {[p['name'] + ' (' + p['model'] + ')' for p in available_providers]}")
        
        if not available_providers:
            raise Exception("No LLM providers found.")

        # Load recent failures from rotator_failures.json to check for cooldown
        script_dir = os.path.dirname(os.path.abspath(__file__))
        failures_path = os.path.join(script_dir, "scratch", "rotator_failures.json")
        recent_failures = {}
        try:
            if os.path.exists(failures_path):
                with open(failures_path, "r", encoding="utf-8") as f:
                    recent_failures = json.load(f)
        except Exception:
            pass

        # Updated failure recording function (supports both models and providers)
        def record_failure(key):
            try:
                recent_failures[key] = time.time()
                os.makedirs(os.path.dirname(failures_path), exist_ok=True)
                with open(failures_path, "w", encoding="utf-8") as f:
                    json.dump(recent_failures, f)
            except Exception:
                pass

        # Reorder if a preferred provider is specified
        if not preferred_provider:
            preferred_provider = os.getenv("PREFERRED_PROVIDER")
            
        # Try loading from agent_state.json if still not set
        if not preferred_provider:
            try:
                state_path = os.path.join(script_dir, "scratch", "agent_state.json")
                if os.path.exists(state_path):
                    with open(state_path, "r", encoding="utf-8") as f:
                        state_data = json.load(f)
                        state_model = state_data.get("model")
                        state_api = state_data.get("api_type")
                        if state_model and state_model != "Автоматична ротація":
                            preferred_provider = state_model
                        elif state_api and state_api != "rotator":
                            preferred_provider = state_api
            except Exception:
                pass

        # Resolve the provider name if preferred_provider is a model name
        preferred_name = preferred_provider
        if preferred_provider:
            for p in available_providers:
                if p["model"] == preferred_provider:
                    preferred_name = p["name"]
                    break

        now = time.time()
        
        # Modified sorting with provider-level cooldown check
        def get_sort_key(x):
            # Check model cooldown
            model_failed_time = recent_failures.get(x["model"], 0)
            model_cooldown = 1 if (now - model_failed_time) < 60 else 0
            
            # Check provider-level cooldown (in case key rate limit is exhausted)
            provider_failed_time = recent_failures.get(f"provider::{x['name']}", 0)
            provider_cooldown = 1 if (now - provider_failed_time) < 60 else 0
            
            is_cooldown = max(model_cooldown, provider_cooldown)
            
            if preferred_provider:
                pref = 0 if x["model"] == preferred_provider else (
                    1 if x["name"] == preferred_name else 2
                )
            else:
                pref = 2
            return (is_cooldown, pref)

        available_providers.sort(key=get_sort_key)

        last_exception = None
        for provider in available_providers:
            # Inline skip check in the loop
            prov_fail = recent_failures.get(f"provider::{provider['name']}", 0)
            mod_fail = recent_failures.get(provider["model"], 0)
            if (now - prov_fail) < 60 or (now - mod_fail) < 60:
                print(f"⏭️ [Rotator] Skipping {provider['name']} ({provider['model']}) due to active cooldown.")
                continue

            try:
                print(f"🤖 [Rotator] Trying provider: {provider['name']} ({provider['model']})")
                client = OpenAI(
                    base_url=provider["base_url"],
                    api_key=provider["api_key"]
                )
                
                params = {
                    "model": provider["model"],
                    "messages": messages,
                }
                
                if response_format:
                    params["response_format"] = response_format

                if "extra_body" in provider:
                    params["extra_body"] = provider["extra_body"]

                start_time = time.time()
                response = client.chat.completions.create(timeout=15.0, **params)
                duration = time.time() - start_time
                
                content = response.choices[0].message.content
                print(f"✅ [Rotator] Success via {provider['name']} in {duration:.2f}s")
                return content

            except Exception as e:
                error_msg = str(e).lower()
                print(f"⚠️ [Rotator] Error with {provider['name']} ({provider['model']}): {e}")
                
                # Always block the current model
                record_failure(provider["model"])
                
                # CRITICAL: If the error is a Rate Limit, block the WHOLE provider
                if any(x in error_msg for x in ["rate limit", "429", "too many requests", "quota exceeded"]):
                    print(f"🚫 [Rotator] Rate limit affects WHOLE provider {provider['name']}. Blocking provider.")
                    record_failure(f"provider::{provider['name']}")
                
                last_exception = e
                continue

        print("❌ [Rotator] All providers failed.")
        if last_exception:
            raise last_exception
        else:
            raise Exception("All LLM providers failed.")

if __name__ == "__main__":
    rotator = LLMRotator()
    try:
        res = rotator.chat_completion([{"role": "user", "content": "Say 'Hello'"}])
        print(f"Result: {res}")
    except Exception as e:
        print(f"Final Error: {e}")
