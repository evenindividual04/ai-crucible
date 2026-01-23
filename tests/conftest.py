"""Pytest fixtures for the AI Crucible tests."""

import pytest
from crucible.state import CrucibleState, DesignComponent, Vulnerability
from crucible.config import CrucibleConfig


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    return CrucibleConfig()


@pytest.fixture
def sample_state():
    """Create a sample state for testing."""
    return CrucibleState(
        user_prompt="Design a URL shortener service",
        max_iterations=3,
    )


@pytest.fixture
def sample_state_with_design():
    """Create a sample state with a design."""
    state = CrucibleState(
        user_prompt="Design a URL shortener service",
        max_iterations=3,
        design_markdown="""# URL Shortener

## Overview
A simple URL shortening service.

## Components
- API Gateway
- URL Store (Redis)
- Redirect Service
""",
        design_components=[
            DesignComponent(
                component_id=1,
                name="API Gateway",
                responsibility="Handle incoming requests",
                assumptions=["Traffic is under 1000 RPS", "All requests are authenticated"],
            ),
            DesignComponent(
                component_id=2,
                name="URL Store",
                responsibility="Store URL mappings in Redis",
                assumptions=["Redis is always available", "Data fits in memory"],
            ),
            DesignComponent(
                component_id=3,
                name="Redirect Service",
                responsibility="Redirect short URLs to original URLs",
                assumptions=["Lookup is O(1)", "No cache invalidation needed"],
            ),
        ],
    )
    state.next_component_id = 4
    return state


@pytest.fixture
def sample_vulnerability():
    """Create a sample vulnerability for testing."""
    return Vulnerability(
        vulnerability_id=1,
        severity="CRITICAL",
        confidence=0.9,
        domain="SECURITY",
        title="SQL Injection in URL validation",
        description="User input is not sanitized before database query",
        attack_vector="Inject malicious SQL via the URL parameter",
        affected_components=[1, 2],
        iteration_found=1,
    )
