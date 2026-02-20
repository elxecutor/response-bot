"""Game-theoretic decision engine for response-bot.

This module implements a lightweight regret-matching strategy mixer that
balances heuristic payoffs from tweet metadata with learned regrets so the
bot gradually leans into the most effective action (reply, quote, or
independent Reddit-inspired post) for each timeline configuration.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Dict, Tuple, Optional

HistoryLoader = Callable[[], Dict]
HistorySaver = Callable[[Dict], None]


class GameTheoryEngine:
    """Repeated-game strategy engine using regret matching."""

    def __init__(
        self,
        state_loader: HistoryLoader,
        state_saver: HistorySaver,
        actions: Tuple[str, ...] | None = None,
    ) -> None:
        self._state_loader = state_loader
        self._state_saver = state_saver
        self.actions: Tuple[str, ...] = actions or (
            "reply",
            "quote",
        )
        self.temperature = 1.2  # Softmax sharpness for payoff-based policy
        self.mixing_factor = 0.55  # Blend between regrets and heuristic best response
        self.failure_penalty = 0.35
        self.state = self._load_or_initialize_state()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def estimate_payoffs(self, tweet: Dict) -> Dict[str, float]:
        """Return heuristic payoffs for each action given tweet metadata."""
        engagement = tweet.get("engagement") or {}
        total_engagement = (
            engagement.get("reply_count", 0) * 1.4
            + engagement.get("quote_count", 0) * 1.2
            + engagement.get("retweet_count", 0)
            + engagement.get("favorite_count", 0) * 0.6
        )

        has_question = bool(tweet.get("has_question"))
        has_media = bool(tweet.get("has_media"))
        has_video = bool(tweet.get("has_video"))
        text_len = len(tweet.get("text", ""))

        # Start with mild priors so every action stays viable
        payoffs = {action: 0.6 for action in self.actions}

        # Reply heuristics
        if "reply" in payoffs:
            if has_question:
                payoffs["reply"] += 1.6
            if total_engagement < 40:
                payoffs["reply"] += 0.6  # early conversation boost
            elif total_engagement > 1000:
                payoffs["reply"] -= 0.4  # avoid loud pile-ons
            # reward media-containing tweets for replies as well
            if has_media:
                payoffs["reply"] += 0.5
            if 60 <= text_len <= 260:
                payoffs["reply"] += 0.2

        # Quote heuristics
        if "quote" in payoffs:
            payoffs["quote"] += 0.3  # baseline preference for stronger signal
            if has_media:
                payoffs["quote"] += 1.0  # stronger boost for visual content
            if has_video:
                payoffs["quote"] += 0.4
            if total_engagement >= 200:
                payoffs["quote"] += 0.3
            if total_engagement <= 30:
                payoffs["quote"] -= 0.2  # Quote tweets feel excessive on low-signal posts

        return {action: round(score, 3) for action, score in payoffs.items()}

    def select_action(self, payoffs: Optional[Dict[str, float]] = None) -> Tuple[str, Dict[str, float]]:
        """Sample an action from the mixed strategy derived from regrets & payoffs."""
        effective_payoffs = payoffs or self.baseline_payoffs()
        distribution = self.mixed_strategy(effective_payoffs)
        chosen = random.choices(
            population=list(distribution.keys()),
            weights=list(distribution.values()),
            k=1,
        )[0]
        return chosen, distribution

    def mixed_strategy(self, payoffs: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """Return the blended strategy distribution without sampling."""
        effective_payoffs = payoffs or self.baseline_payoffs()
        regret_policy = self._regret_policy()
        payoff_policy = self._softmax_policy(effective_payoffs)

        weights = {}
        for action in self.actions:
            blended = (
                self.mixing_factor * regret_policy.get(action, 0.0)
                + (1 - self.mixing_factor) * payoff_policy.get(action, 0.0)
            )
            weights[action] = max(blended, 1e-6)
        return self._normalize(weights)

    def baseline_payoffs(self) -> Dict[str, float]:
        """Lightweight priors so the engine can pick before inspecting a tweet."""
        base = {action: 1.0 for action in self.actions}
        if 'reply' in base:
            base['reply'] += 0.25
        if 'quote' in base:
            base['quote'] += 0.1
        return base

    def update_regret(self, payoffs: Dict[str, float], chosen_action: str) -> None:
        """Update cumulative regrets after we observe the counterfactual payoffs."""
        chosen_payoff = payoffs.get(chosen_action, 0.0)
        regrets = self.state.setdefault("regret", {})

        for action in self.actions:
            current = regrets.get(action, 0.0)
            regret_delta = payoffs.get(action, 0.0) - chosen_payoff
            regrets[action] = max(0.0, current + regret_delta)

        strategy_counts = self.state.setdefault("strategy_counts", {})
        strategy_counts[chosen_action] = strategy_counts.get(chosen_action, 0.0) + 1.0
        self.state["iterations"] = self.state.get("iterations", 0) + 1
        self._persist_state()

    def penalize_failure(self, action: str) -> None:
        """Apply a mild regret boost when an action fails to execute."""
        regrets = self.state.setdefault("regret", {})
        regrets[action] = max(0.0, regrets.get(action, 0.0) - self.failure_penalty)
        self._persist_state()

    def diagnostics(self) -> Dict[str, float]:
        regrets = self.state.get("regret", {})
        return {
            action: round(regrets.get(action, 0.0), 3)
            for action in self.actions
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_or_initialize_state(self) -> Dict:
        history = self._state_loader() or {}
        game_state = history.get("game_theory") or {}

        regret = game_state.get("regret", {})
        strategy_counts = game_state.get("strategy_counts", {})
        for action in self.actions:
            regret.setdefault(action, 0.0)
            strategy_counts.setdefault(action, 1.0)
        game_state["regret"] = regret
        game_state["strategy_counts"] = strategy_counts
        game_state.setdefault("iterations", 0)

        history["game_theory"] = game_state
        self._state_saver(history)
        return game_state

    def _persist_state(self) -> None:
        history = self._state_loader() or {}
        history["game_theory"] = self.state
        self._state_saver(history)

    def _regret_policy(self) -> Dict[str, float]:
        regrets = self.state.get("regret", {})
        positives = {a: max(regrets.get(a, 0.0), 0.0) for a in self.actions}
        total = sum(positives.values())
        if total <= 0:
            return {a: 1.0 / len(self.actions) for a in self.actions}
        return {a: positives[a] / total for a in self.actions}

    def _softmax_policy(self, payoffs: Dict[str, float]) -> Dict[str, float]:
        values = [payoffs.get(a, 0.0) for a in self.actions]
        max_val = max(values) if values else 0.0
        exps = [math.exp((payoffs.get(a, 0.0) - max_val) / self.temperature) for a in self.actions]
        total = sum(exps) or 1.0
        return {action: exps[idx] / total for idx, action in enumerate(self.actions)}

    @staticmethod
    def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
        total = sum(weights.values()) or 1.0
        return {action: weight / total for action, weight in weights.items()}


__all__ = ["GameTheoryEngine"]
