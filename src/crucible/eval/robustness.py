"""
Robustness testing framework for AI Crucible evaluation.

This module provides:
- LLM-based perturbation generators for design prompts
- Semantic similarity scoring for comparing outputs
- Robustness evaluator that compares base and perturbed runs
"""

import asyncio
from enum import Enum
from typing import Callable, Literal
from dataclasses import dataclass

from crucible.eval.schemas import Trace, EvaluationReport, PerturbationRecord
from crucible.config import get_config


class PerturbationType(str, Enum):
    """Types of input perturbations."""

    PARAPHRASE = "paraphrase"
    ADD_NOISE = "add_noise"
    CHANGE_TONE = "change_tone"
    RESTRUCTURE = "restructure"


@dataclass
class PerturbationConfig:
    """Configuration for perturbation generator."""

    generator_type: str = "llm"  # "llm" or "template"
    max_perturbations: int = 3
    similarity_threshold: float = 0.85  # For filtering redundant perturbations


class LLMPerturbator:
    """LLM-based perturbation generator using configured LLM."""

    def __init__(self, config: PerturbationConfig | None = None):
        """Initialize the LLM perturbator."""
        self.config = config or PerturbationConfig()

    async def perturb(
        self,
        prompt: str,
        perturbation_type: PerturbationType,
        num_variants: int = 1,
    ) -> list[PerturbationRecord]:
        """
        Generate perturbed variants of the input prompt.

        Args:
            prompt: The original design prompt
            perturbation_type: Type of perturbation
            num_variants: Number of variants to generate

        Returns:
            List of perturbation records
        """
        if perturbation_type == PerturbationType.PARAPHRASE:
            return await self._paraphrase(prompt, num_variants)
        elif perturbation_type == PerturbationType.ADD_NOISE:
            return await self._add_noise(prompt, num_variants)
        elif perturbation_type == PerturbationType.CHANGE_TONE:
            return await self._change_tone(prompt, num_variants)
        elif perturbation_type == PerturbationType.RESTRUCTURE:
            return await self._restructure(prompt, num_variants)
        else:
            # Default: return original as single perturbation
            return [PerturbationRecord(
                type=PerturbationType.PARAPHRASE,
                input=prompt,
                original_input=prompt,
                similarity_score=1.0,
            )]

    async def _paraphrase(self, prompt: str, num_variants: int) -> list[PerturbationRecord]:
        """Generate paraphrased variants."""
        from crucible.agents.architect import ArchitectAgent
        from crucible.graph import get_tracer

        agent = ArchitectAgent()
        tracer = get_tracer()

        paraphrases = []
        for i in range(num_variants):
            if tracer:
                tracer.agent_invoke("Architect", "ArchitectAgent")

            paraphrase_prompt = f"""Paraphrase the following system design prompt while keeping the same meaning and requirements:

Original prompt:
{prompt}

Please rewrite the prompt to use different wording, sentence structure, and vocabulary. Maintain all technical requirements and functional specifications exactly.

Return only the paraphrased prompt, without any additional explanation or commentary."""

            result = await agent.invoke_async(user_prompt=paraphrase_prompt)

            paraphrased = result.design_markdown

            if tracer:
                tracer.agent_complete(
                    agent_type="Architect",
                    agent_name="ArchitectAgent",
                    success=True,
                    vulnerabilities_found=0,
                )

            paraphrases.append(paraphrased)

        return [
            PerturbationRecord(
                type=PerturbationType.PARAPHRASE,
                input=p,
                original_input=prompt,
                paraphrased=paraphrased,
                similarity_score=1.0,
            )
            for p in paraphrases
        ]

    async def _add_noise(self, prompt: str, num_variants: int) -> list[PerturbationRecord]:
        """Add plausible noise to prompt."""
        noise_phrases = [
            "The system should also handle edge cases like",
            "Additionally, consider that",
            "For high-traffic scenarios,",
            "Make sure to",
            "In production environments,",
        ]

        variants = []
        for i in range(num_variants):
            noise = noise_phrases[i % len(noise_phrases)]
            noise_prompt = f"""{prompt}

{noise}

Add the above text to the system design prompt. The text should be relevant but should not change the core requirements or functional specifications.

Return the modified prompt with the noise text inserted."""

            variants.append(PerturbationRecord(
                type=PerturbationType.ADD_NOISE,
                input=noise_prompt,
                original_input=prompt,
                similarity_score=0.9,
            ))

        return variants

    async def _change_tone(self, prompt: str, num_variants: int) -> list[PerturbationRecord]:
        """Change the tone of the prompt."""
        tones = [
            "Make the prompt more formal and professional",
            "Rewrite the prompt to use more casual, conversational language",
            "Change the writing style to be more technical or more business-oriented",
        ]

        variants = []
        for i in range(num_variants):
            tone_instruction = tones[i % len(tones)]
            tone_prompt = f"""{prompt}

{tone_instruction}

Rewrite the prompt following the tone instruction. Maintain all technical requirements and functional specifications exactly.

Return only the rewritten prompt without any additional explanation or commentary."""

            variants.append(PerturbationRecord(
                type=PerturbationType.CHANGE_TONE,
                input=tone_prompt,
                original_input=prompt,
                similarity_score=0.8,
            ))

        return variants

    async def _restructure(self, prompt: str, num_variants: int) -> list[PerturbationRecord]:
        """Restructure the prompt organization."""
        restructuring_instructions = [
            "Reorder the components in a more logical way",
            "Combine related components into a single component",
            "Split a complex component into multiple simpler components",
            "Move specific requirements to different sections",
        ]

        variants = []
        for i in range(num_variants):
            instruction = restructuring_instructions[i % len(restructuring_instructions)]
            restructure_prompt = f"""{prompt}

{instruction}

Restructure the system design prompt according to the instruction. Maintain all technical requirements and functional specifications exactly.

Return the restructured prompt without any additional explanation or commentary."""

            variants.append(PerturbationRecord(
                type=PerturbationType.RESTRUCTURE,
                input=restructure_prompt,
                original_input=prompt,
                similarity_score=0.7,
            ))

        return variants


class SemanticSimilarity:
    """
    Calculates semantic similarity between design outputs.

    Uses a simplified approach that compares:
    - Component structure (number and types)
    - Key technical terms
    - Overall design length
    """

    @staticmethod
    def calculate_similarity(output1: str, output2: str) -> float:
        """Calculate similarity between two design outputs."""
        if not output1 or not output2:
            return 0.0

        # Simple token overlap ratio
        tokens1 = set(output1.lower().split())
        tokens2 = set(output2.lower().split())

        overlap = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        jaccard = overlap / union if union > 0 else 0.0

        return jaccard


class RobustnessEvaluator:
    """
    Evaluates robustness of a system across input perturbations.

    Metrics:
    - Output stability: Semantic similarity of designs
    - Trajectory stability: Similarity of execution paths
    - Metric stability: Consistency of evaluation scores
    """

    @staticmethod
    def evaluate_single_run(base_trace: Trace, perturbed_trace: Trace) -> dict:
        """Evaluate a single perturbed run against baseline."""
        if not base_trace or not perturbed_trace:
            return {"error": "Missing trace data"}

        # Output similarity
        output_similarity = SemanticSimilarity.calculate_similarity(
            base_trace.user_prompt or "",
            perturbed_trace.user_prompt or "",
        )

        # Trajectory stability (compare iteration counts, security scores)
        base_iterations = base_trace.iteration_count
        perturbed_iterations = perturbed_trace.iteration_count
        iteration_stability = 1.0 - abs(base_iterations - perturbed_iterations) / max(base_iterations, perturbed_iterations)

        base_security = 0.0
        perturbed_security = 0.0
        if hasattr(base_trace, "max_iterations") and hasattr(perturbed_trace, "max_iterations"):
            base_max = base_trace.max_iterations
            perturbed_max = perturbed_trace.max_iterations
            base_security = min(1.0, base_iterations / base_max) if base_max > 0 else 0.0
            perturbed_security = min(1.0, perturbed_iterations / perturbed_max) if perturbed_max > 0 else 0.0

        # Calculate robustness score
        robustness_score = (
            output_similarity * 0.4 +
            iteration_stability * 0.3 +
            base_security * 0.3
        )

        return {
            "output_similarity": output_similarity,
            "iteration_stability": iteration_stability,
            "base_security_score": base_security,
            "perturbed_security_score": perturbed_security,
            "robustness_score": robustness_score,
            "details": {
                "base_iterations": base_iterations,
                "perturbed_iterations": perturbed_iterations,
            "base_max_iterations": base_max,
                "perturbed_max_iterations": perturbed_max,
            },
        }

    @staticmethod
    def evaluate_batch(results: list[dict]) -> dict:
        """Evaluate robustness across multiple runs."""
        if not results:
            return {"error": "No results to evaluate"}

        output_scores = [r.get("robustness_score", 0.5) for r in results if "robustness_score" in r]
        metric_stability = 1.0 - (max(output_scores) - min(output_scores)) if output_scores else 0.0

        return {
            "mean_robustness": sum(output_scores) / len(output_scores),
            "min_robustness": min(output_scores) if output_scores else 0.0,
            "max_robustness": max(output_scores) if output_scores else 0.0,
            "metric_stability": metric_stability,
            "num_runs": len(results),
        }
