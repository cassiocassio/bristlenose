# LLM Provider Implementation Details (Archive)

_Shipped implementation records for Ollama, Azure OpenAI, and Keychain integration. Moved here from `design-cli-improvements.md` during documentation refactor (Feb 2026). All phases below are either completed or contain implementation sketches used during development._

_For the current provider status and what's still open (Gemini), see `docs/design-cli-improvements.md`._

---

### Current Architecture

The `LLMClient` in `bristlenose/llm/client.py` uses a dispatch pattern:

```python
async def analyze(self, system_prompt, user_prompt, response_model, max_tokens):
    if self.provider == "anthropic":
        return await self._analyze_anthropic(...)
    elif self.provider == "openai":
        return await self._analyze_openai(...)
    else:
        raise ValueError(f"Unsupported LLM provider: {self.provider}")
```

Each provider has:
1. **Lazy client initialisation** — SDK client created on first use
2. **Structured output mechanism** — tool use (Anthropic) or JSON mode (OpenAI)
3. **Token tracking** — normalised to `input_tokens`/`output_tokens`

Adding a new provider requires changes in 5 locations:
1. `config.py` — add API key field, add alias
2. `llm/client.py` — add dispatch branch, add implementation method
3. `llm/pricing.py` — add model pricing
4. `doctor.py` — add API key validation
5. Tests

### Priority 1: Azure OpenAI

**Why:** Many enterprises have Microsoft 365 E5 or Azure contracts that include Azure OpenAI. They can't use consumer OpenAI API keys; they must route through their Azure subscription for compliance, billing, and data residency reasons.

**Key insight:** Azure OpenAI uses the same models (GPT-4o, GPT-4o-mini) but with a different authentication and endpoint scheme. The OpenAI Python SDK supports Azure natively via `AsyncAzureOpenAI` — we don't need a separate SDK.

**Implementation complexity: LOW** — copy-paste from `_analyze_openai()` with 4 line changes.

#### Configuration

```python
# In config.py
class BristlenoseSettings(BaseSettings):
    # Existing
    llm_provider: str = "anthropic"
    openai_api_key: str = ""

    # New for Azure (4 fields)
    azure_openai_endpoint: str = ""      # https://my-resource.openai.azure.com/
    azure_openai_key: str = ""           # API key from Azure portal
    azure_openai_deployment: str = ""    # Deployment name (NOT model name!)
    azure_openai_api_version: str = "2024-10-21"  # Use latest stable

# Add aliases
_LLM_PROVIDER_ALIASES = {
    "claude": "anthropic",
    "chatgpt": "openai",
    "gpt": "openai",
    "azure": "azure",           # NEW
    "azure-openai": "azure",    # NEW
}
```

#### Implementation

The implementation is nearly identical to `_analyze_openai()` — just swap the client class and add Azure-specific params:

```python
# In llm/client.py — add to __init__
self._azure_client: object | None = None

# In _validate_api_key() — add branch
if self.provider == "azure":
    if not self.settings.azure_openai_endpoint:
        raise ValueError(
            "Azure OpenAI endpoint not set. "
            "Set BRISTLENOSE_AZURE_OPENAI_ENDPOINT to your resource URL."
        )
    if not self.settings.azure_openai_key:
        raise ValueError(
            "Azure OpenAI API key not set. "
            "Set BRISTLENOSE_AZURE_OPENAI_KEY from your Azure portal."
        )
    if not self.settings.azure_openai_deployment:
        raise ValueError(
            "Azure OpenAI deployment not set. "
            "Set BRISTLENOSE_AZURE_OPENAI_DEPLOYMENT to your model deployment name."
        )

# In analyze() — add dispatch branch
elif self.provider == "azure":
    return await self._analyze_azure(
        system_prompt, user_prompt, response_model, max_tokens
    )

# New method (copy of _analyze_openai with 4 changes highlighted)
async def _analyze_azure(
    self,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int,
) -> T:
    """Call Azure OpenAI API with JSON mode for structured output."""
    import openai

    if self._azure_client is None:
        # CHANGE 1: AsyncAzureOpenAI instead of AsyncOpenAI
        # CHANGE 2: azure_endpoint and api_version params
        self._azure_client = openai.AsyncAzureOpenAI(
            api_key=self.settings.azure_openai_key,
            azure_endpoint=self.settings.azure_openai_endpoint,
            api_version=self.settings.azure_openai_api_version,
        )

    client: openai.AsyncAzureOpenAI = self._azure_client  # type: ignore[assignment]

    schema = response_model.model_json_schema()
    schema_instruction = (
        f"\n\nYou must respond with valid JSON matching this schema:\n"
        f"```json\n{json.dumps(schema, indent=2)}\n```"
    )

    logger.debug("Calling Azure OpenAI API: deployment=%s", self.settings.azure_openai_deployment)

    response = await client.chat.completions.create(
        # CHANGE 3: deployment name instead of model name
        model=self.settings.azure_openai_deployment,
        max_tokens=max_tokens,
        temperature=self.settings.llm_temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + schema_instruction},
            {"role": "user", "content": user_prompt},
        ],
    )

    if hasattr(response, "usage") and response.usage:
        self.tracker.record(response.usage.prompt_tokens, response.usage.completion_tokens)

    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("Empty response from Azure OpenAI")

    data = json.loads(content)
    return response_model.model_validate(data)
```

**Total new code: ~35 lines** (method is 90% identical to OpenAI).

#### Key Differences from Regular OpenAI

| Aspect | OpenAI | Azure OpenAI |
|--------|--------|--------------|
| Client class | `AsyncOpenAI` | `AsyncAzureOpenAI` |
| Auth | `api_key` only | `api_key` + `azure_endpoint` + `api_version` |
| Model param | Model name (`gpt-4o`) | Deployment name (`my-gpt4o-deployment`) |
| API versions | Implicit | Explicit (`2024-10-21`, `2025-03-01-preview`) |

**Gotcha:** Azure uses deployment names, not model names. A user might deploy GPT-4o as `"research-model"` or `"gpt4o-eastus"`. The deployment name is set in Azure portal when they create the deployment.

#### Doctor Validation

```python
def _validate_azure_key(endpoint: str, key: str, deployment: str, api_version: str) -> tuple[bool | None, str]:
    """Validate Azure OpenAI credentials.

    Azure doesn't have a simple /models endpoint, so we make a minimal
    completion request with max_tokens=1 to verify credentials work.
    """
    import httpx

    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions"
    headers = {"api-key": key, "Content-Type": "application/json"}
    params = {"api-version": api_version}
    body = {
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 1,
    }

    try:
        response = httpx.post(url, headers=headers, params=params, json=body, timeout=10)
        if response.status_code == 200:
            return True, ""
        elif response.status_code == 401:
            return False, "Invalid API key"
        elif response.status_code == 404:
            return False, f"Deployment '{deployment}' not found"
        else:
            return False, f"Azure returned {response.status_code}: {response.text[:100]}"
    except httpx.ConnectError:
        return None, f"Cannot connect to {endpoint}"
```

#### Pricing

Azure OpenAI pricing is roughly equivalent to OpenAI consumer pricing but varies by:
- Region (East US cheaper than West Europe)
- Commitment tier (pay-as-you-go vs provisioned throughput)

For cost estimation, we'll use OpenAI rates as a baseline. Add to `pricing.py`:

```python
# Azure uses deployment names, not model names, so we can't look up directly.
# Cost estimation for Azure will return None (unknown) unless user configures
# BRISTLENOSE_AZURE_MODEL_EQUIVALENT to map their deployment to a model name.
```

Alternatively, add a config field `azure_openai_model_equivalent` so users can specify which model their deployment uses for cost estimation.

#### User Experience

```bash
# Environment variables
export BRISTLENOSE_LLM_PROVIDER=azure
export BRISTLENOSE_AZURE_OPENAI_ENDPOINT=https://my-resource.openai.azure.com/
export BRISTLENOSE_AZURE_OPENAI_KEY=abc123...
export BRISTLENOSE_AZURE_OPENAI_DEPLOYMENT=gpt-4o-research

# CLI usage
bristlenose run ./interviews --llm azure

# Or in .env file:
BRISTLENOSE_LLM_PROVIDER=azure
BRISTLENOSE_AZURE_OPENAI_ENDPOINT=https://my-resource.openai.azure.com/
BRISTLENOSE_AZURE_OPENAI_KEY=abc123...
BRISTLENOSE_AZURE_OPENAI_DEPLOYMENT=gpt-4o-research
```

#### GitHub Copilot Clarification

GitHub Copilot ≠ Azure OpenAI. They're different products:

- **Copilot** is IDE-integrated code completion. No public inference API. The [copilot-api](https://github.com/ericc-ch/copilot-api) reverse-engineering project exists but violates ToS and risks account suspension.
- **Azure OpenAI** is the API service for GPT models. Available to Azure subscribers.
- **GitHub Enterprise + Copilot** customers can usually get Azure OpenAI access through their Microsoft relationship.

**Recommendation:** Don't support Copilot directly. Point enterprise users to Azure OpenAI instead.

#### Testing Checklist

1. Unit tests:
   - [ ] `_validate_api_key()` raises for missing endpoint/key/deployment
   - [ ] `_analyze_azure()` dispatches correctly
   - [ ] Response parsing and token tracking work

2. Integration test (requires Azure credentials):
   - [ ] Real API call with a simple prompt
   - [ ] Structured output matches Pydantic schema

3. Doctor tests:
   - [ ] `check_api_key()` handles azure provider
   - [ ] Validation function handles 401/404/network errors

### Priority 2: Google Gemini

**Why:** Google Cloud Platform customers often have Gemini access through their GCP billing. Some organisations are Google-first and don't have Azure or Anthropic relationships. Additionally, Gemini 2.5 Flash is 5–7× cheaper than Claude/GPT-4o, appealing to cost-conscious users.

**Implementation complexity: MEDIUM** — new SDK, different async pattern, some known limitations.

#### Configuration

```python
# In config.py
class BristlenoseSettings(BaseSettings):
    # New for Gemini (2 fields)
    google_api_key: str = ""                   # From Google AI Studio or GCP
    gemini_model: str = "gemini-2.5-flash"     # Default to Flash (cheap + capable)

# Add aliases
_LLM_PROVIDER_ALIASES = {
    ...
    "gemini": "gemini",    # NEW
    "google": "gemini",    # NEW
}
```

#### New Dependency

Gemini requires a new package:

```toml
# In pyproject.toml
dependencies = [
    ...
    "google-genai>=1.0.0",  # NEW — Google Gen AI SDK
]
```

**Size impact:** ~15 MB (includes protobuf, grpcio, google-auth). Not trivial, but acceptable.

#### Implementation

```python
# In llm/client.py — add to __init__
self._gemini_client: object | None = None

# In _validate_api_key() — add branch
if self.provider == "gemini" and not self.settings.google_api_key:
    raise ValueError(
        "Google API key not set. "
        "Set BRISTLENOSE_GOOGLE_API_KEY from Google AI Studio or GCP console."
    )

# In analyze() — add dispatch branch
elif self.provider == "gemini":
    return await self._analyze_gemini(
        system_prompt, user_prompt, response_model, max_tokens
    )

# New method
async def _analyze_gemini(
    self,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int,
) -> T:
    """Call Google Gemini API with native JSON schema support.

    Unlike Anthropic (tool use) and OpenAI (JSON mode), Gemini supports
    Pydantic-derived JSON schemas natively via response_schema config.
    """
    from google import genai

    if self._gemini_client is None:
        self._gemini_client = genai.Client(api_key=self.settings.google_api_key)

    # Gemini SDK uses .aio property for async client access
    client = self._gemini_client.aio

    # Gemini accepts JSON schema directly — cleaner than tool use workaround
    schema = response_model.model_json_schema()

    logger.debug("Calling Gemini API: model=%s", self.settings.gemini_model)

    # Gemini combines system + user prompts differently
    # The official pattern is to include system instructions in contents
    response = await client.models.generate_content(
        model=self.settings.gemini_model,
        contents=f"{system_prompt}\n\n{user_prompt}",
        config={
            "response_mime_type": "application/json",
            "response_schema": schema,
            "max_output_tokens": max_tokens,
            "temperature": self.settings.llm_temperature,
        },
    )

    # Token tracking — Gemini uses different field names
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        self.tracker.record(
            response.usage_metadata.prompt_token_count or 0,
            response.usage_metadata.candidates_token_count or 0,
        )

    # Parse response
    if not response.text:
        raise RuntimeError("Empty response from Gemini")

    data = json.loads(response.text)
    return response_model.model_validate(data)
```

#### Key Differences from Claude/OpenAI

| Aspect | Claude | OpenAI | Gemini |
|--------|--------|--------|--------|
| Structured output | Tool use (force tool call) | JSON mode + schema in prompt | Native `response_schema` |
| Async client | `AsyncAnthropic()` | `AsyncOpenAI()` | `Client().aio` |
| System prompt | Separate `system=` param | First message role=system | Combined with user content |
| Token fields | `input_tokens`, `output_tokens` | `prompt_tokens`, `completion_tokens` | `prompt_token_count`, `candidates_token_count` |

#### Known SDK Limitations

The `google-genai` SDK has some rough edges as of v1.5.0:

1. **Dict handling in schemas** — `dict[str, T]` types can cause issues ([googleapis/python-genai#460](https://github.com/googleapis/python-genai/issues/460)). Our Pydantic models use `list` not `dict` for collections, so should be fine.

2. **Async context management** — Must call `await client.aclose()` or use `async with` context manager. We'll use lazy init + no explicit close (like our other providers), which may leak connections. Consider adding cleanup in future.

3. **Error messages** — Less descriptive than Anthropic/OpenAI. May need extra logging for debugging.

**Mitigation:** Test thoroughly with our actual Pydantic models (`SpeakerRoleAssignment`, `TopicSegmentationResult`, `QuoteExtractionResult`, etc.) before shipping.

#### Pricing

Add to `pricing.py`:

```python
PRICING: dict[str, tuple[float, float]] = {
    # ... existing ...
    # Gemini
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.30, 2.50),      # Best value
    "gemini-2.5-flash-lite": (0.10, 0.40),  # Ultra cheap
}

PRICING_URLS: dict[str, str] = {
    # ... existing ...
    "gemini": "https://ai.google.dev/gemini-api/docs/pricing",
}
```

#### Doctor Validation

```python
def _validate_google_key(key: str) -> tuple[bool | None, str]:
    """Validate Google API key by listing available models."""
    import httpx

    url = "https://generativelanguage.googleapis.com/v1/models"
    params = {"key": key}

    try:
        response = httpx.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return True, ""
        elif response.status_code == 400:
            return False, "Invalid API key format"
        elif response.status_code == 403:
            return False, "API key rejected — check it's enabled for Gemini API"
        else:
            return False, f"Google returned {response.status_code}"
    except httpx.ConnectError:
        return None, "Cannot connect to Google API"
```

#### User Experience

```bash
# Environment variable
export BRISTLENOSE_LLM_PROVIDER=gemini
export BRISTLENOSE_GOOGLE_API_KEY=AIza...

# CLI usage
bristlenose run ./interviews --llm gemini

# Use cheaper Flash model (default)
bristlenose run ./interviews --llm gemini

# Use Pro for higher quality
bristlenose run ./interviews --llm gemini --model gemini-2.5-pro
```

**Cost comparison for 5 interviews:**
- Claude Sonnet: ~$1.50
- GPT-4o: ~$1.00
- **Gemini Flash: ~$0.20** (5–7× cheaper)

#### Testing Checklist

1. Unit tests:
   - [ ] `_validate_api_key()` raises for missing key
   - [ ] `_analyze_gemini()` dispatches correctly
   - [ ] Token tracking handles Gemini's field names
   - [ ] Response parsing works with our Pydantic models

2. Integration test (requires Google API key):
   - [ ] Real API call with `QuoteExtractionResult` schema
   - [ ] Verify all 5 stage schemas work

3. Edge cases:
   - [ ] Empty response handling
   - [ ] Schema with nested objects
   - [ ] Long context (>100K tokens)

### Priority 3: Local Models (Ollama)

**Why:** Air-gapped environments, data sovereignty requirements, or users who want to avoid API costs entirely.

**Approach:** Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1/`. We can use the standard OpenAI SDK pointed at a local endpoint.

**Configuration:**

```python
# In config.py
class BristlenoseSettings(BaseSettings):
    # New for local
    local_model_url: str = "http://localhost:11434/v1"  # Default to Ollama
    local_model_name: str = "llama3.2"  # Model name in Ollama

# Add alias
_LLM_PROVIDER_ALIASES = {
    ...
    "local": "local",
    "ollama": "local",
}
```

**Implementation:**

```python
# In llm/client.py
async def _analyze_local(
    self,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int,
) -> T:
    """Call local Ollama-compatible API with JSON mode.

    Uses the OpenAI SDK pointed at a local endpoint.
    """
    import openai

    if self._local_client is None:
        self._local_client = openai.AsyncOpenAI(
            base_url=self.settings.local_model_url,
            api_key="ollama",  # Required but ignored by Ollama
        )

    client: openai.AsyncOpenAI = self._local_client

    # Same JSON mode approach as OpenAI
    schema = response_model.model_json_schema()
    schema_instruction = (
        f"\n\nYou must respond with valid JSON matching this schema:\n"
        f"```json\n{json.dumps(schema, indent=2)}\n```"
    )

    response = await client.chat.completions.create(
        model=self.settings.local_model_name,
        max_tokens=max_tokens,
        temperature=self.settings.llm_temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + schema_instruction},
            {"role": "user", "content": user_prompt},
        ],
    )

    # Token tracking (Ollama provides this)
    if hasattr(response, "usage") and response.usage:
        self.tracker.record(response.usage.prompt_tokens, response.usage.completion_tokens)

    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("Empty response from local model")

    data = json.loads(content)
    return response_model.model_validate(data)
```

**Key considerations:**
- Ollama runs on `localhost:11434` by default
- The API key is required by the SDK but ignored by Ollama (set to `"ollama"`)
- JSON mode support depends on the model — function-calling models (Llama 3.1+, Mistral, Qwen 2.5) work best
- Smaller models may struggle with complex schemas; may need prompt engineering
- No API cost, but local inference is slower and less capable

**Doctor check:** Validate that the local endpoint is reachable:

```python
def _validate_local_model(url: str, model: str) -> tuple[bool | None, str]:
    """Check that Ollama is running and the model is available."""
    try:
        response = httpx.get(f"{url}/models", timeout=5)
        if response.status_code != 200:
            return False, f"Local model server returned {response.status_code}"
        models = response.json().get("data", [])
        if not any(m.get("id") == model for m in models):
            return False, f"Model '{model}' not found. Run: ollama pull {model}"
        return True, ""
    except httpx.ConnectError:
        return False, "Cannot connect to local model server. Is Ollama running?"
```

**Pricing:** Local models are free (no API cost). `estimate_cost()` returns `None` for local provider.

---

### Ollama as Zero-Friction Entry Point

**The problem:** API keys are a barrier to trying the tool. Users must:
1. Create an account with Anthropic or OpenAI
2. Add payment details
3. Generate and copy an API key
4. Figure out where to put it

Many potential users bounce at step 1-2. This is a significant adoption barrier.

**The solution:** Make Ollama the "just try it" path — no signup, no payment, no keys.

#### First-Run Experience (Proposed)

```
bristlenose run ./interviews

Bristlenose v0.7.0

No LLM provider configured. Choose one:

  [1] Local AI (free, private, slower)
      Requires Ollama — install from https://ollama.ai

  [2] Claude API (best quality, ~$1.50/study)
      Get a key from console.anthropic.com

  [3] ChatGPT API (good quality, ~$1.00/study)
      Get a key from platform.openai.com

Choice [1]:
```

If they choose [1] and Ollama isn't installed:

```
Ollama not found.

Install it from: https://ollama.ai
(It's a single download, no account needed)

After installing, run:
  ollama pull llama3.2

Then try again:
  bristlenose run ./interviews

Press Enter to open the download page...
```

If Ollama is installed but no suitable model:

```
Ollama is running, but no suitable model found.

Downloading llama3.2 (2.0 GB)...
████████████████████████████████████████ 100%

Ready! Starting with local AI.
```

If everything is ready:

```
Running with local AI (llama3.2)
This is slower than cloud APIs but completely free and private.
For best quality, run: bristlenose config set-key claude

  ✓ Ingested 5 sessions                          0.1s
  ✓ Extracted audio                              12.3s
  ...
```

#### Why This Works

1. **Zero signup** — no account creation, no email, no payment
2. **Privacy reinforcement** — "completely free and private" echoes our core pitch
3. **Low commitment** — try before deciding if it's worth $1.50/study
4. **Graceful upgrade path** — once they see value, "bristlenose config set-key claude" is easy
5. **Works offline** — useful for researchers in the field or on planes

#### Model Recommendations

Based on [Ollama's structured output documentation](https://ollama.com/blog/structured-outputs), these models work well with JSON schemas:

| Model | Download | RAM | Quality | Speed | Notes |
|-------|----------|-----|---------|-------|-------|
| **llama3.2:3b** | 2.0 GB | ~4 GB | Good | Fast | **Default** — fits most laptops |
| **llama3.2:1b** | 1.3 GB | ~2 GB | OK | Very fast | For older machines, Chromebooks |
| **mistral:7b** | 4.1 GB | ~8 GB | Better | Medium | Better reasoning |
| **qwen2.5:7b** | 4.4 GB | ~8 GB | Better | Medium | Good multilingual (CJK) |
| **llama3.1:8b** | 4.7 GB | ~8 GB | Best | Slower | Closest to cloud quality |

**Default: `llama3.2:3b`**

Rationale:
- 2 GB download is tolerable for first-time users
- 4 GB RAM requirement fits most modern laptops (8 GB total)
- Good enough for structured output tasks
- Fast enough that users see results quickly

#### Quality Trade-offs (Be Honest in Messaging)

Local models are genuinely worse than Claude/GPT-4o for our tasks:

| Aspect | Claude Sonnet | llama3.2:3b | Notes |
|--------|---------------|-------------|-------|
| JSON schema compliance | ~99% | ~85% | May need retries |
| Quote extraction | Nuanced | Good | Misses subtle insights |
| Speaker identification | Excellent | Good | Occasional confusion |
| Theme grouping | Excellent | OK | Less coherent themes |
| Speed (5 interviews) | ~2 min | ~10 min | On M2 MacBook |

**Key insight:** For a first try, "good enough to see if the tool is useful" is sufficient. Users who see value will upgrade to cloud APIs for production runs.

**Messaging in CLI output:**

```
Running with local AI (llama3.2)
This is slower and less accurate than cloud APIs, but completely free and private.
For production quality, run: bristlenose config set-key claude
```

The message is honest about trade-offs while suggesting the upgrade path.

#### Implementation Details

**Ollama detection:**

```python
def check_ollama() -> tuple[bool, str, str | None]:
    """Check if Ollama is running and has a suitable model.

    Returns:
        (is_available, message, recommended_model)
    """
    import httpx

    try:
        # Check Ollama is running
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code != 200:
            return False, "Ollama not responding", None

        models = r.json().get("models", [])

        # Look for suitable models in priority order
        preferred = ["llama3.2:3b", "llama3.2", "llama3.1:8b", "mistral:7b", "qwen2.5:7b"]
        for model in preferred:
            if any(m["name"].startswith(model.split(":")[0]) for m in models):
                return True, f"Found {model}", model

        # Check for any llama/mistral/qwen model
        suitable = [m["name"] for m in models if any(
            m["name"].startswith(p) for p in ["llama", "mistral", "qwen"]
        )]
        if suitable:
            return True, f"Found {suitable[0]}", suitable[0]

        return False, "No suitable model found", None

    except httpx.ConnectError:
        return False, "Ollama not running", None
```

**Auto-pull model with progress:**

```python
import subprocess
import sys

def pull_model(model: str = "llama3.2:3b") -> bool:
    """Pull model from Ollama registry. Shows progress to user."""
    console.print(f"Downloading {model}...")
    console.print("[dim]This may take a few minutes depending on your connection.[/dim]")

    result = subprocess.run(
        ["ollama", "pull", model],
        stdout=sys.stdout,  # Show Ollama's progress bar
        stderr=sys.stderr,
    )

    if result.returncode == 0:
        console.print(f"[green]✓[/green] Downloaded {model}")
        return True
    else:
        console.print(f"[red]Failed to download {model}[/red]")
        return False
```

**Retry logic for structured output failures:**

Local models sometimes produce malformed JSON. Add retry with backoff:

```python
async def _analyze_local_with_retry(
    self,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int,
    max_retries: int = 3,
) -> T:
    """Call local model with retry for JSON parsing failures."""
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await self._analyze_openai_compatible(
                system_prompt, user_prompt, response_model, max_tokens
            )
        except json.JSONDecodeError as e:
            last_error = e
            logger.debug(f"JSON parse failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))  # Backoff

    raise RuntimeError(
        f"Local model failed to produce valid JSON after {max_retries} attempts. "
        f"Last error: {last_error}. "
        f"Try a larger model (--model llama3.1:8b) or use cloud API."
    )
```

**First-run flow integration:**

```python
def _prompt_for_provider() -> str:
    """Interactive prompt when no provider is configured."""
    console.print()
    console.print("[bold]No LLM provider configured.[/bold] Choose one:")
    console.print()
    console.print("  [1] Local AI (free, private, slower)")
    console.print("      [dim]Requires Ollama — https://ollama.ai[/dim]")
    console.print()
    console.print("  [2] Claude API (best quality, ~$1.50/study)")
    console.print("      [dim]Get a key from console.anthropic.com[/dim]")
    console.print()
    console.print("  [3] ChatGPT API (good quality, ~$1.00/study)")
    console.print("      [dim]Get a key from platform.openai.com[/dim]")
    console.print()

    choice = Prompt.ask("Choice", choices=["1", "2", "3"], default="1")

    if choice == "1":
        return _setup_local_provider()
    elif choice == "2":
        console.print()
        console.print("Get your API key from: [link]https://console.anthropic.com/settings/keys[/link]")
        console.print("Then run: [bold]bristlenose config set-key claude[/bold]")
        raise typer.Exit(0)
    else:  # choice == "3"
        console.print()
        console.print("Get your API key from: [link]https://platform.openai.com/api-keys[/link]")
        console.print("Then run: [bold]bristlenose config set-key chatgpt[/bold]")
        raise typer.Exit(0)

def _setup_local_provider() -> str:
    """Set up local provider, pulling model if needed."""
    is_available, message, model = check_ollama()

    if not is_available and "not running" in message:
        console.print()
        console.print("[yellow]Ollama not found.[/yellow]")
        console.print()
        console.print("Install it from: [link]https://ollama.ai[/link]")
        console.print("[dim](It's a single download, no account needed)[/dim]")
        console.print()
        console.print("After installing, run:")
        console.print("  [bold]ollama pull llama3.2[/bold]")
        console.print()
        console.print("Then try again:")
        console.print("  [bold]bristlenose run ./interviews[/bold]")
        console.print()

        if Confirm.ask("Open the download page?", default=True):
            import webbrowser
            webbrowser.open("https://ollama.ai")

        raise typer.Exit(0)

    if not is_available and "No suitable model" in message:
        console.print()
        console.print("[yellow]Ollama is running, but no suitable model found.[/yellow]")
        console.print()
        if Confirm.ask("Download llama3.2 (2.0 GB)?", default=True):
            if pull_model("llama3.2:3b"):
                return "local"
            else:
                raise typer.Exit(1)
        raise typer.Exit(0)

    # Ready to go
    console.print()
    console.print(f"[green]✓[/green] Using local AI ({model})")
    console.print("[dim]This is slower than cloud APIs but completely free and private.[/dim]")
    console.print("[dim]For production quality: bristlenose config set-key claude[/dim]")
    console.print()

    return "local"
```

#### Doctor Integration

Update `bristlenose doctor` to show Ollama status:

```
bristlenose doctor

  FFmpeg          ok   7.1
  Whisper         ok   MLX (Apple Silicon)
  LLM provider    ok   Local (llama3.2:3b via Ollama)
                       [dim]For best quality: bristlenose config set-key claude[/dim]
```

Or if no API key and no Ollama:

```
bristlenose doctor

  FFmpeg          ok   7.1
  Whisper         ok   MLX (Apple Silicon)
  LLM provider    !!   No provider configured
                       Quick start (free): install Ollama from https://ollama.ai
                       Best quality: bristlenose config set-key claude
```

#### Requirements Summary

To make Ollama the "just try it" path:

1. **Ollama detection** — check if running, find suitable models
2. **Interactive first-run prompt** — offer choices, guide setup
3. **Model auto-pull** — download default model with consent
4. **Retry logic** — handle JSON parsing failures gracefully
5. **Honest messaging** — be clear about quality trade-offs
6. **Doctor integration** — show local provider status

**Effort estimate:** ~4-5 hours (including testing with different models)

**Priority:** HIGH — this removes the biggest adoption barrier. A user who can try the tool for free in 10 minutes is more likely to eventually become a paying cloud API user.

---

### macOS Keychain Integration

**Why:** macOS is likely the primary platform for our user base (researchers, designers). Storing API keys in `.env` files is:
1. **Insecure** — plain text on disk, easy to accidentally commit to git
2. **Inconvenient** — manual copy-paste, separate file per project
3. **Non-standard** — macOS users expect credentials in Keychain

**Goal:** `bristlenose` should read API keys from macOS Keychain automatically, with `.env`/environment as fallback.

#### Implementation Options

**Option A: Use `keyring` library (recommended)**

The [`keyring`](https://pypi.org/project/keyring/) library provides cross-platform credential storage with native macOS Keychain support.

```python
# In config.py — add fallback chain
def _get_api_key(service: str, env_var: str, settings_field: str) -> str:
    """Get API key from Keychain, then env var, then settings field."""
    # 1. Try Keychain (macOS/Windows/Linux secret service)
    try:
        import keyring
        key = keyring.get_password("bristlenose", service)
        if key:
            return key
    except Exception:
        pass  # keyring not available or failed

    # 2. Try environment variable
    key = os.environ.get(env_var, "")
    if key:
        return key

    # 3. Fall back to settings (from .env file)
    return settings_field

# Usage in BristlenoseSettings or LLMClient:
anthropic_key = _get_api_key("anthropic", "BRISTLENOSE_ANTHROPIC_API_KEY", settings.anthropic_api_key)
```

**CLI for setting keys:**

```bash
# Store key in Keychain
bristlenose config set-key anthropic
# Prompts: Enter your Claude API key: ********
# Stores in Keychain as service="bristlenose", username="anthropic"

# Or one-liner
bristlenose config set-key anthropic --value sk-ant-...

# List configured providers
bristlenose config list-keys
# anthropic  ✓ (Keychain)
# openai     ✓ (env var)
# azure      ✗ (not configured)

# Remove key
bristlenose config delete-key anthropic
```

**Implementation:**

```python
# New file: bristlenose/keychain.py
"""Keychain integration for secure API key storage."""

import sys

def _get_keyring():
    """Get keyring module, or None if unavailable."""
    try:
        import keyring
        # Verify backend is available (not the "fail" backend)
        if keyring.get_keyring().__class__.__name__ == "Keyring":
            return None  # No real backend
        return keyring
    except ImportError:
        return None

def get_key(service: str) -> str | None:
    """Get API key from system keyring."""
    kr = _get_keyring()
    if kr is None:
        return None
    try:
        return kr.get_password("bristlenose", service)
    except Exception:
        return None

def set_key(service: str, key: str) -> bool:
    """Store API key in system keyring. Returns True on success."""
    kr = _get_keyring()
    if kr is None:
        return False
    try:
        kr.set_password("bristlenose", service, key)
        return True
    except Exception:
        return False

def delete_key(service: str) -> bool:
    """Remove API key from system keyring. Returns True on success."""
    kr = _get_keyring()
    if kr is None:
        return False
    try:
        kr.delete_password("bristlenose", service)
        return True
    except Exception:
        return False

def list_keys() -> dict[str, bool]:
    """Return dict of service -> is_configured."""
    services = ["anthropic", "openai", "azure", "google"]
    return {s: get_key(s) is not None for s in services}
```

**Dependency:**

```toml
# In pyproject.toml — optional dependency
[project.optional-dependencies]
keychain = ["keyring>=25.0.0"]

# Or make it a regular dependency (adds ~1 MB)
dependencies = [
    ...
    "keyring>=25.0.0",
]
```

**Security note from keyring docs:**
> Any Python script can access secrets created by keyring from that same Python executable without the OS prompting for a password.

This is acceptable for CLI tools. For higher security, users can configure Keychain Access to require password on each access.

#### Option B: Direct macOS `security` command (no dependency)

Use subprocess to call macOS `security` CLI directly:

```python
import subprocess

def get_key_macos(service: str) -> str | None:
    """Get key from macOS Keychain using security CLI."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "bristlenose", "-a", service, "-w"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None  # Not found

def set_key_macos(service: str, key: str) -> bool:
    """Store key in macOS Keychain using security CLI."""
    try:
        # Delete existing (ignore if not found)
        subprocess.run(
            ["security", "delete-generic-password", "-s", "bristlenose", "-a", service],
            capture_output=True, check=False,
        )
        # Add new
        subprocess.run(
            ["security", "add-generic-password", "-s", "bristlenose", "-a", service, "-w", key],
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False
```

**Pros:** No dependency, macOS-native
**Cons:** macOS only, shell escaping risks, less robust

**Recommendation:** Use `keyring` library — it's well-maintained, cross-platform, and handles edge cases properly.

#### Integration with `doctor` Command

Update `bristlenose doctor` to show Keychain status:

```
  API key        ok   Claude (Keychain)
  API key        ok   ChatGPT (env var)
```

Or with warning:

```
  API key        !!   API key in .env file — consider using Keychain
                      Run: bristlenose config set-key anthropic
```

#### Priority

**Do after Azure + Gemini providers.** Keychain is a UX improvement, not a blocker. Users can still use `.env` files. But it should come before v1.0.0 since it's table stakes for a Mac-native tool.

**Effort:** ~3 hours (including CLI commands and doctor integration)

### Implementation Order (Revised — Ollama First)

The zero-friction entry point is the highest value feature for adoption. Build Ollama support first, then layer on enterprise providers.

**Phase 1: Foundation + Ollama (~5 hours)** ← START HERE
1. Create `bristlenose/providers.py` with `ProviderSpec` registry
2. Refactor `LLMClient` to use registry + `_analyze_openai_compatible()`
3. Add Local (Ollama) provider with detection and retry logic
4. Add first-run interactive prompt when no provider configured
5. Add model auto-pull with progress display
6. Update doctor to show Ollama status and guide users

**Why Ollama first:**
- Removes biggest adoption barrier (API key requirement)
- Uses OpenAI SDK — same code path tests the abstraction
- Zero new dependencies (unlike Gemini)
- Users can try the tool for free immediately

**Phase 2: Azure OpenAI (~2 hours)**
1. Add Azure to registry (same SDK as Ollama, different client config)
2. Add doctor validation for Azure credentials
3. Test with enterprise deployment

**Phase 3: ✅ Keychain Integration — DONE**
1. ✅ Created `bristlenose/credentials.py` (abstraction), `credentials_macos.py` (macOS Keychain via `security` CLI), `credentials_linux.py` (Linux Secret Service via `secret-tool`)
2. ✅ Added `bristlenose configure <provider>` CLI command with `--key` option
3. ✅ Updated credential loading to check Keychain first (priority: keychain → env var → .env)
4. ✅ Updated doctor to show "(Keychain)" suffix when key comes from keychain
5. ✅ Validates keys before storing — catches typos/truncation
6. ✅ Tests in `tests/test_credentials.py` (25 tests)

**Phase 4: Gemini (~3 hours)**
1. Add `google-genai` dependency
2. Add Gemini to registry
3. Add `_analyze_gemini()` method (different SDK pattern)
4. Test with all 5 Pydantic schemas

**Phase 5: Documentation + Polish (~2 hours)**
1. Update README with "Choosing an LLM provider" section
2. Update `bristlenose help config` with all providers
3. Update man page
4. Add provider examples to `.env.example`

**Total: ~15 hours**

The order prioritises:
1. ✅ **Adoption** (Ollama removes the biggest barrier) — DONE
2. **Enterprise** (Azure unblocks corporate users)
3. ✅ **UX polish** (Keychain secure credential storage) — DONE
4. **Budget option** (Gemini is cheaper but requires new SDK)

---

### Files to Create/Modify

```
bristlenose/
├── providers.py          # ✅ DONE: ProviderSpec, PROVIDERS registry, resolve_provider()
├── credentials.py        # ✅ DONE: CredentialStore ABC, EnvCredentialStore fallback, get_credential()
├── credentials_macos.py  # ✅ DONE: MacOSCredentialStore using `security` CLI
├── credentials_linux.py  # ✅ DONE: LinuxCredentialStore using `secret-tool`, fallback to env
├── config.py             # ✅ DONE: loads from keychain via _populate_keys_from_keychain()
├── llm/
│   ├── client.py         # MODIFY: use registry, add _analyze_openai_compatible(), _analyze_gemini()
│   └── pricing.py        # MODIFY: add Gemini models, use registry for URLs
├── cli.py                # ✅ DONE: added `configure` command
└── doctor.py             # ✅ DONE: shows key source (Keychain vs env)

tests/
├── test_providers.py     # ✅ DONE: registry tests, alias resolution (47 tests)
├── test_credentials.py   # ✅ DONE: credential store tests (25 tests)
└── test_llm_client.py    # MODIFY: test new providers with mocked SDKs
```

### Testing Strategy

Each provider needs:
1. **Unit tests** — mock the SDK, test dispatch and parsing
2. **Integration tests** (optional, requires credentials) — real API calls
3. **Doctor tests** — validation logic

For local models, add a CI job that runs Ollama in Docker and tests with a small model.

### Documentation

Update:
- `bristlenose doctor` output to show which providers are configured
- `bristlenose help config` to list all provider env vars
- Man page with provider configuration examples
- README with "Enterprise deployment" section

### Won't do

- **Context-aware API key errors** (#4) — current messages are fine
- **`--force` flag** (#3) — `render` command already handles this use case
- **Cap Typer help width** (#11) — no clean hook, accept inconsistency
- **Full `--dry-run`** (#9) — time estimate warning is more useful
