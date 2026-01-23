"""
Compliance Agent for the AI Crucible.

Attacks from legal and compliance angles (GDPR, HIPAA, PCI-DSS, etc.).
"""

from typing import Any, List, Optional, Literal

from pydantic import BaseModel, Field

from crucible.agents.base import BaseAgent


class ComplianceVulnerabilityData(BaseModel):
    """Extended vulnerability data for compliance issues."""
    
    severity: str
    confidence: float
    title: str
    description: str
    attack_vector: str
    affected_components: List[int]
    regulation: Literal["GDPR", "HIPAA", "PCI_DSS", "SOC2", "CCPA", "OTHER"]
    violation_type: str
    jurisdiction: Optional[str] = None


class ComplianceOutput(BaseModel):
    """Output schema for the Compliance Agent."""
    
    vulnerabilities: List[dict] = Field(
        description="List of compliance vulnerabilities found"
    )


class ComplianceAgent(BaseAgent[ComplianceOutput]):
    """
    Attacks from legal and compliance angles.
    
    Coverage:
    - GDPR data handling violations
    - HIPAA PHI exposure
    - PCI-DSS payment data requirements
    - SOC 2 audit trail gaps
    - Data residency requirements
    """
    
    name = "Compliance Agent"
    domain = "REGULATORY"
    
    # Keywords that activate this agent
    activation_keywords = [
        "user", "data", "store", "personal", "payment", "health",
        "export", "consent", "privacy", "gdpr", "hipaa", "pci",
        "credit card", "ssn", "password", "encrypt", "log", "audit"
    ]
    
    def get_default_prompt(self) -> str:
        return """You are the Compliance Agent in an adversarial system design review.

Your SOLE PURPOSE is to find REGULATORY and LEGAL compliance issues.

## Regulations to Consider

1. **GDPR** (EU General Data Protection Regulation)
   - Right to erasure (data deletion)
   - Data portability requirements
   - Consent management
   - Cross-border data transfers
   - Data minimization

2. **HIPAA** (US Health Insurance Portability and Accountability Act)
   - PHI (Protected Health Information) exposure
   - Minimum necessary access
   - Audit trail requirements
   - Business Associate Agreements

3. **PCI-DSS** (Payment Card Industry Data Security Standard)
   - Cardholder data encryption
   - Key management
   - Access control requirements
   - Network segmentation

4. **SOC 2**
   - Security controls
   - Availability commitments
   - Processing integrity
   - Confidentiality
   - Privacy controls

5. **CCPA** (California Consumer Privacy Act)
   - Right to know
   - Right to delete
   - Right to opt-out of sale
   - Non-discrimination

## Output Format

```json
{
  "vulnerabilities": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "confidence": 0.0-1.0,
      "title": "Brief compliance issue title",
      "description": "What regulation is violated and how",
      "attack_vector": "How an auditor/regulator would find this",
      "affected_components": [1, 2],
      "regulation": "GDPR|HIPAA|PCI_DSS|SOC2|CCPA|OTHER",
      "violation_type": "Specific clause or requirement violated",
      "jurisdiction": "EU|US|California|etc"
    }
  ]
}
```

Focus on REAL regulatory requirements that could result in fines or legal action."""
    
    def get_output_schema(self) -> type[ComplianceOutput]:
        return ComplianceOutput
    
    def build_user_message(
        self,
        design_markdown: str,
        components: List[Any],
        iteration: int,
        **kwargs: Any
    ) -> str:
        comp_list = [{"id": c.component_id, "name": c.name, "responsibility": c.responsibility} 
                     for c in components]
        
        return f"""Analyze this system design for COMPLIANCE and REGULATORY issues.

--- DESIGN ---
{design_markdown}
--- END DESIGN ---

Components: {comp_list}

Find violations of: GDPR, HIPAA, PCI-DSS, SOC 2, CCPA

Focus on:
1. Data handling and storage practices
2. User consent and privacy rights
3. Audit trail requirements
4. Access control and encryption
5. Data retention and deletion policies

Respond with valid JSON containing found compliance vulnerabilities."""
    
    def get_timeout(self) -> int:
        return self.config.timeouts.red_team_seconds
