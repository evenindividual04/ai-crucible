"""
Keyword-based router for activating Red Team agents.

Uses heuristic keyword matching to determine which agents
should attack the given design.
"""

from typing import List, Set

from crucible.state import CrucibleState, DesignComponent


# Keyword mappings from graph-logic.md
AGENT_KEYWORDS: dict[str, Set[str]] = {
    "SecurityHawk": {
        "auth", "login", "password", "token", "session", "oauth", "jwt",
        "api_key", "encrypt", "sql", "injection", "xss", "csrf", "admin",
        "permission", "role", "access", "secret", "credential", "hash",
        "ssl", "tls", "https", "certificate", "signature", "verify",
    },
    "ScaleMonster": {
        "database", "cache", "redis", "queue", "traffic", "concurrent",
        "scale", "replica", "shard", "partition", "load", "cluster",
        "distributed", "async", "parallel", "thread", "pool", "connection",
        "memory", "cpu", "throughput", "latency", "batch", "stream",
    },
    "CostAnalyst": {
        "api", "cloud", "lambda", "storage", "bandwidth", "compute",
        "tier", "pricing", "usage", "metered", "quota", "limit",
        "pay", "subscription", "billing", "credits", "resources",
        "external", "third-party", "saas", "egress",
    },
    "LogicBreaker": {
        "state", "transaction", "order", "sequence", "lock", "mutex",
        "deadlock", "race", "async", "event", "workflow", "status",
        "transition", "validate", "constraint", "invariant", "atomic",
        "rollback", "compensate", "saga", "idempotent",
    },
    # V2 Agents
    "ComplianceAgent": {
        "user", "data", "store", "personal", "payment", "health",
        "export", "consent", "privacy", "gdpr", "hipaa", "pci",
        "credit", "ssn", "password", "encrypt", "log", "audit",
        "retain", "delete", "portable", "cookie", "tracking",
    },
    "UXAdversary": {
        "ui", "frontend", "mobile", "user", "form", "input", "display",
        "button", "page", "screen", "interface", "web", "app", "view",
        "error", "loading", "slow", "timeout", "accessibility", "a11y",
    },
    "ChaosEngineer": {
        "distributed", "microservice", "api", "database", "queue", "cache",
        "timeout", "retry", "partition", "replica", "cluster", "failover",
        "async", "eventual", "consistency", "transaction", "network",
        "unavailable", "degraded", "circuit", "breaker",
    },
}


class KeywordRouter:
    """
    Routes agents based on keyword analysis of the design.
    
    If no keywords match, activates ALL agents (conservative approach).
    """
    
    def __init__(self, keywords: dict[str, Set[str]] | None = None):
        self.keywords = keywords or AGENT_KEYWORDS
    
    def route(self, state: CrucibleState) -> List[str]:
        """
        Determine which agents to activate based on the design.
        
        Returns a list of agent names to activate.
        """
        # Collect all text to search
        text_sources = [
            state.user_prompt.lower(),
            state.design_markdown.lower(),
        ]
        
        # Add component text
        for comp in state.design_components:
            text_sources.append(comp.name.lower())
            text_sources.append(comp.responsibility.lower())
            for assumption in comp.assumptions:
                text_sources.append(assumption.lower())
        
        combined_text = " ".join(text_sources)
        
        # Find matching agents
        activated: Set[str] = set()
        
        for agent_name, keywords in self.keywords.items():
            for keyword in keywords:
                if keyword in combined_text:
                    activated.add(agent_name)
                    break  # One match is enough
        
        # If no agents matched, activate all (conservative)
        if not activated:
            activated = set(self.keywords.keys())
        
        return sorted(list(activated))
    
    def explain_routing(self, state: CrucibleState) -> dict[str, List[str]]:
        """
        Explain which keywords triggered each agent.
        
        Useful for debugging and transparency.
        """
        text_sources = [
            state.user_prompt.lower(),
            state.design_markdown.lower(),
        ]
        
        for comp in state.design_components:
            text_sources.append(comp.name.lower())
            text_sources.append(comp.responsibility.lower())
        
        combined_text = " ".join(text_sources)
        
        explanation: dict[str, List[str]] = {}
        
        for agent_name, keywords in self.keywords.items():
            matched = [kw for kw in keywords if kw in combined_text]
            if matched:
                explanation[agent_name] = matched[:5]  # Top 5 matches
        
        return explanation


def route_agents(state: CrucibleState) -> List[str]:
    """Convenience function to route agents for a state."""
    router = KeywordRouter()
    return router.route(state)
