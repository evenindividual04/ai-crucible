"""
Attack templates and chaining for the AI Crucible.

Provides pre-built attack patterns and vulnerability chaining.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class AttackTier(Enum):
    """Progressive depth of analysis."""
    
    SURFACE = 1       # Obvious issues, quick wins (OWASP Top 10)
    STRUCTURAL = 2    # Component interaction bugs
    CREATIVE = 3      # Novel attack vectors
    ADVERSARIAL = 4   # Assumes attacker has internal knowledge


@dataclass
class VulnerabilityTemplate:
    """Template for a common vulnerability pattern."""
    
    title: str
    description: str
    attack_vector: str
    severity: str
    domain: str
    keywords: List[str] = field(default_factory=list)
    tier: AttackTier = AttackTier.SURFACE


@dataclass
class AttackTemplate:
    """Pre-built attack patterns for common system types."""
    
    system_type: str
    description: str
    activation_keywords: List[str]
    vulnerabilities: List[VulnerabilityTemplate]


@dataclass
class ChainedVulnerability:
    """A vulnerability that builds on others."""
    
    vulnerability_id: int
    title: str
    description: str
    prerequisite_vulnerability_ids: List[int]
    chain_description: str
    combined_severity: str
    combined_confidence: float


# Pre-built attack templates for common system types
ATTACK_TEMPLATES: Dict[str, AttackTemplate] = {
    "payment_system": AttackTemplate(
        system_type="Payment System",
        description="Financial transaction processing systems",
        activation_keywords=["payment", "money", "transaction", "wallet", "transfer", "balance", "credit"],
        vulnerabilities=[
            VulnerabilityTemplate(
                title="Double Spend via Race Condition",
                description="Concurrent requests can spend the same balance twice",
                attack_vector="Send two payment requests simultaneously",
                severity="CRITICAL",
                domain="SECURITY",
                keywords=["balance", "spend", "concurrent"],
                tier=AttackTier.STRUCTURAL,
            ),
            VulnerabilityTemplate(
                title="TOCTOU in Balance Check",
                description="Time-of-check to time-of-use gap allows overdraft",
                attack_vector="Check balance, then spend more before deduction",
                severity="CRITICAL",
                domain="SECURITY",
                keywords=["balance", "check", "deduct"],
                tier=AttackTier.STRUCTURAL,
            ),
            VulnerabilityTemplate(
                title="Refund Abuse",
                description="Refund can be requested multiple times for same transaction",
                attack_vector="Replay refund request with same transaction ID",
                severity="HIGH",
                domain="LOGIC",
                keywords=["refund", "return", "reverse"],
                tier=AttackTier.CREATIVE,
            ),
            VulnerabilityTemplate(
                title="Currency Rounding Exploitation",
                description="Rounding errors accumulate to steal fractions",
                attack_vector="Perform many small transactions that round favorably",
                severity="MEDIUM",
                domain="LOGIC",
                keywords=["currency", "decimal", "cents"],
                tier=AttackTier.CREATIVE,
            ),
        ],
    ),
    "auth_system": AttackTemplate(
        system_type="Authentication System",
        description="User authentication and session management",
        activation_keywords=["login", "auth", "password", "session", "token", "oauth", "jwt"],
        vulnerabilities=[
            VulnerabilityTemplate(
                title="Session Fixation",
                description="Attacker can set victim's session ID before login",
                attack_vector="Pre-set session cookie, trick user to login",
                severity="CRITICAL",
                domain="SECURITY",
                keywords=["session", "cookie", "login"],
                tier=AttackTier.STRUCTURAL,
            ),
            VulnerabilityTemplate(
                title="Token Leakage in Logs",
                description="JWT or session tokens logged in server logs",
                attack_vector="Access logs to steal authentication tokens",
                severity="HIGH",
                domain="SECURITY",
                keywords=["jwt", "token", "log"],
                tier=AttackTier.SURFACE,
            ),
            VulnerabilityTemplate(
                title="Brute Force Without Rate Limiting",
                description="No protection against password guessing attacks",
                attack_vector="Automated password guessing with wordlist",
                severity="HIGH",
                domain="SECURITY",
                keywords=["password", "login", "attempt"],
                tier=AttackTier.SURFACE,
            ),
            VulnerabilityTemplate(
                title="Privilege Escalation via Role Manipulation",
                description="User can modify their role in request payload",
                attack_vector="Change role field in authentication request",
                severity="CRITICAL",
                domain="SECURITY",
                keywords=["role", "admin", "permission"],
                tier=AttackTier.STRUCTURAL,
            ),
        ],
    ),
    "messaging_system": AttackTemplate(
        system_type="Chat/Messaging System",
        description="Real-time messaging and communication",
        activation_keywords=["chat", "message", "send", "receive", "notification", "push"],
        vulnerabilities=[
            VulnerabilityTemplate(
                title="Message Ordering Violation",
                description="Messages arrive out of order, causing confusion",
                attack_vector="Send messages rapidly or exploit network latency",
                severity="MEDIUM",
                domain="LOGIC",
                keywords=["message", "order", "sequence"],
                tier=AttackTier.STRUCTURAL,
            ),
            VulnerabilityTemplate(
                title="Delivery Guarantee Failure",
                description="Messages can be lost without notification",
                attack_vector="Kill connection during message send",
                severity="HIGH",
                domain="RELIABILITY",
                keywords=["send", "deliver", "ack"],
                tier=AttackTier.STRUCTURAL,
            ),
            VulnerabilityTemplate(
                title="Presence Information Leakage",
                description="User online status exposed to unauthorized users",
                attack_vector="Query presence API without authentication",
                severity="MEDIUM",
                domain="SECURITY",
                keywords=["online", "status", "presence"],
                tier=AttackTier.SURFACE,
            ),
        ],
    ),
    "file_storage": AttackTemplate(
        system_type="File Storage System",
        description="File upload, storage, and retrieval",
        activation_keywords=["file", "upload", "download", "storage", "s3", "blob", "attachment"],
        vulnerabilities=[
            VulnerabilityTemplate(
                title="Path Traversal",
                description="Access files outside allowed directory",
                attack_vector="Use ../ sequences in file path",
                severity="CRITICAL",
                domain="SECURITY",
                keywords=["path", "file", "directory"],
                tier=AttackTier.SURFACE,
            ),
            VulnerabilityTemplate(
                title="Quota Bypass",
                description="Upload more than allowed storage quota",
                attack_vector="Upload many small files or use compression tricks",
                severity="MEDIUM",
                domain="LOGIC",
                keywords=["quota", "limit", "size"],
                tier=AttackTier.STRUCTURAL,
            ),
            VulnerabilityTemplate(
                title="Metadata Leakage",
                description="File metadata reveals sensitive information",
                attack_vector="Access file metadata API to enumerate users",
                severity="MEDIUM",
                domain="SECURITY",
                keywords=["metadata", "owner", "created"],
                tier=AttackTier.SURFACE,
            ),
        ],
    ),
    "api_gateway": AttackTemplate(
        system_type="API Gateway",
        description="API routing and management",
        activation_keywords=["api", "gateway", "route", "endpoint", "rest", "graphql"],
        vulnerabilities=[
            VulnerabilityTemplate(
                title="Rate Limit Bypass",
                description="Circumvent rate limiting by changing identifiers",
                attack_vector="Rotate IP addresses or API keys",
                severity="HIGH",
                domain="SECURITY",
                keywords=["rate", "limit", "throttle"],
                tier=AttackTier.STRUCTURAL,
            ),
            VulnerabilityTemplate(
                title="Header Injection",
                description="Inject malicious headers into downstream requests",
                attack_vector="Add headers that bypass security controls",
                severity="HIGH",
                domain="SECURITY",
                keywords=["header", "inject", "forward"],
                tier=AttackTier.STRUCTURAL,
            ),
            VulnerabilityTemplate(
                title="API Version Confusion",
                description="Access deprecated/vulnerable API versions",
                attack_vector="Change version number in URL path",
                severity="MEDIUM",
                domain="SECURITY",
                keywords=["version", "deprecated", "v1"],
                tier=AttackTier.SURFACE,
            ),
        ],
    ),
}


def get_relevant_templates(keywords: List[str]) -> List[AttackTemplate]:
    """Get attack templates relevant to the given keywords."""
    relevant = []
    keywords_lower = [k.lower() for k in keywords]
    
    for template in ATTACK_TEMPLATES.values():
        for activation_kw in template.activation_keywords:
            if activation_kw in keywords_lower:
                relevant.append(template)
                break
    
    return relevant


def suggest_attack_chains(
    vulnerabilities: List[dict],
    templates: List[AttackTemplate]
) -> List[ChainedVulnerability]:
    """
    Analyze vulnerabilities and suggest attack chains.
    
    Looks for vulnerabilities that can be combined for greater impact.
    """
    chains = []
    
    # Group by domain
    by_domain = {}
    for v in vulnerabilities:
        domain = v.get("domain", "UNKNOWN")
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(v)
    
    # Look for security + scalability chains (DoS amplification)
    security_vulns = by_domain.get("SECURITY", [])
    scale_vulns = by_domain.get("SCALABILITY", [])
    
    for sec in security_vulns:
        for scale in scale_vulns:
            if any(c in sec.get("affected_components", []) 
                   for c in scale.get("affected_components", [])):
                chain = ChainedVulnerability(
                    vulnerability_id=-1,  # To be assigned
                    title=f"{sec.get('title', 'Security Issue')} → {scale.get('title', 'Scale Issue')}",
                    description=f"Combining {sec.get('title')} with {scale.get('title')} amplifies impact",
                    prerequisite_vulnerability_ids=[
                        sec.get("vulnerability_id", 0),
                        scale.get("vulnerability_id", 0)
                    ],
                    chain_description="Security vulnerability enables scalability attack",
                    combined_severity="CRITICAL",
                    combined_confidence=0.8,
                )
                chains.append(chain)
    
    return chains


def get_tier_vulnerabilities(
    tier: AttackTier,
    templates: List[AttackTemplate]
) -> List[VulnerabilityTemplate]:
    """Get all vulnerability templates for a specific tier."""
    vulns = []
    for template in templates:
        for v in template.vulnerabilities:
            if v.tier == tier:
                vulns.append(v)
    return vulns
