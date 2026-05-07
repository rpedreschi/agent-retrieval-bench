# Models

The headline benchmark reports against two models:

- `anthropic/claude-opus-4-7` (short: `claude-opus-4-7`)
- `openai/gpt-5` (short: `gpt-5`)

Both are listed in `arb.eval.models.MODELS`. Running the eval requires the
matching API key in the environment:

- `ANTHROPIC_API_KEY` for Anthropic models.
- `OPENAI_API_KEY` for OpenAI models.

Inspect AI reads these directly; the harness never threads keys through code.

## Swapping or adding a model

Two ways to point the harness at a different model:

### 1. Add it to the registry (preferred for repeated use)

Open `src/arb/eval/models.py` and append to `MODELS`:

```python
"my-model": ModelSpec(
    name="anthropic/claude-haiku-4-5",   # the Inspect AI provider/id string
    short="my-model",                     # how it appears in result tables
    family="anthropic",
),
```

Then list it in `config/eval.yaml`:

```yaml
models:
  - claude-opus-4-7
  - gpt-5
  - my-model
```

### 2. Pass an Inspect AI string directly (one-off runs)

`arb.eval.models.resolve()` accepts a fully-qualified Inspect AI string
(`"<family>/<id>"`). Put it straight into `config/eval.yaml`:

```yaml
models:
  - "google/gemini-2.5-pro"
```

The result row's `model` field is the part after the slash.

## Choosing a different model family

Any model Inspect AI supports works as long as the corresponding API key is
exported. Tool-use behaviour varies between families; if a model fails the
multi-hop task category disproportionately, that is a useful finding — log
it; don't tune the prompt to compensate. The methodology guarantees that
agent system prompts are identical across variants and models.

## Headline numbers

Headline numbers in the blog post and talks are reported against
`claude-opus-4-7` and `gpt-5` only. Other models are valid for forker
exploration; do not republish results from non-headline models without
clearly tagging them as such.
