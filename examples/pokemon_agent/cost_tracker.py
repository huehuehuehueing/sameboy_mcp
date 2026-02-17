"""LLM API cost tracking for the Pokemon agent.

Tracks token usage and calculates costs for OpenAI and Anthropic APIs.
"""

from dataclasses import dataclass, field


# Pricing per 1M tokens (as of 2025)
OPENAI_PRICING = {
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40, "cached_input": 0.025},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60, "cached_input": 0.10},
    "gpt-4.1": {"input": 2.00, "output": 8.00, "cached_input": 0.50},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cached_input": 0.075},
    "gpt-4o": {"input": 2.50, "output": 10.00, "cached_input": 1.25},
}

ANTHROPIC_PRICING = {
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00, "cached_input": 0.30},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00, "cached_input": 0.08},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00, "cached_input": 1.50},
}


@dataclass
class CostTracker:
    """Tracks LLM API token usage and costs."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0
    total_cost: float = 0.0
    _step_costs: list[float] = field(default_factory=list)

    def track_openai(self, usage, model: str) -> float:
        """Track costs from an OpenAI API response usage object.

        Args:
            usage: The usage object from OpenAI response (has prompt_tokens, completion_tokens)
            model: Model name string

        Returns:
            Cost for this step in dollars
        """
        if usage is None:
            return 0.0

        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        cached_tokens = getattr(usage, "prompt_tokens_details", None)
        cached = 0
        if cached_tokens and hasattr(cached_tokens, "cached_tokens"):
            cached = cached_tokens.cached_tokens or 0

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cached_tokens += cached

        # Find pricing - try exact match first, then prefix match
        pricing = self._find_pricing(model, OPENAI_PRICING)

        non_cached = input_tokens - cached
        step_cost = (
            non_cached * pricing["input"]
            + cached * pricing["cached_input"]
            + output_tokens * pricing["output"]
        ) / 1_000_000

        self.total_cost += step_cost
        self._step_costs.append(step_cost)
        return step_cost

    def track_anthropic(self, usage, model: str) -> float:
        """Track costs from an Anthropic API response usage object.

        Args:
            usage: The usage object from Anthropic response
            model: Model name string

        Returns:
            Cost for this step in dollars
        """
        if usage is None:
            return 0.0

        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cached_tokens += cached

        pricing = self._find_pricing(model, ANTHROPIC_PRICING)

        non_cached = input_tokens - cached
        step_cost = (
            non_cached * pricing["input"]
            + cached * pricing["cached_input"]
            + output_tokens * pricing["output"]
        ) / 1_000_000

        self.total_cost += step_cost
        self._step_costs.append(step_cost)
        return step_cost

    def _find_pricing(self, model: str, table: dict) -> dict:
        """Find pricing for a model, with prefix matching fallback."""
        if model in table:
            return table[model]
        # Try prefix match (e.g., "gpt-4o-mini-2025-01-01" matches "gpt-4o-mini")
        for key in table:
            if model.startswith(key) or key.startswith(model):
                return table[key]
        # Default: use middle-tier pricing as estimate
        return {"input": 1.0, "output": 5.0, "cached_input": 0.10}

    @property
    def step_count(self) -> int:
        return len(self._step_costs)

    @property
    def avg_step_cost(self) -> float:
        if not self._step_costs:
            return 0.0
        return self.total_cost / len(self._step_costs)

    def summary(self) -> str:
        """Return a human-readable cost summary."""
        lines = [
            f"Total cost: ${self.total_cost:.4f}",
            f"Steps tracked: {self.step_count}",
            f"Avg cost/step: ${self.avg_step_cost:.6f}",
            f"Tokens - input: {self.total_input_tokens:,} | output: {self.total_output_tokens:,} | cached: {self.total_cached_tokens:,}",
        ]
        return "\n".join(lines)
