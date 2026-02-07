"""
Compliance and standards mapping for AI Crucible.

Maps vulnerabilities to OWASP Top 10 and CWE (Common Weakness Enumeration).
"""

from typing import List, Dict, Set
from dataclasses import dataclass, field
from crucible.state import CrucibleState, Vulnerability


# OWASP Top 10 2021
OWASP_TOP_10_2021 = {
    "A01": "Broken Access Control",
    "A02": "Cryptographic Failures",
    "A03": "Injection",
    "A04": "Insecure Design",
    "A05": "Security Misconfiguration",
    "A06": "Vulnerable and Outdated Components",
    "A07": "Identification and Authentication Failures",
    "A08": "Software and Data Integrity Failures",
    "A09": "Security Logging and Monitoring Failures",
    "A10": "Server-Side Request Forgery (SSRF)",
}


# Common CWE mappings (Top 25 most dangerous)
CWE_DATABASE = {
    79: "Cross-site Scripting (XSS)",
    89: "SQL Injection",
    20: "Improper Input Validation",
    78: "OS Command Injection",
    190: "Integer Overflow or Wraparound",
    22: "Path Traversal",
    352: "Cross-Site Request Forgery (CSRF)",
    434: "Unrestricted Upload of File with Dangerous Type",
    306: "Missing Authentication for Critical Function",
    862: "Missing Authorization",
    798: "Use of Hard-coded Credentials",
    287: "Improper Authentication",
    295: "Improper Certificate Validation",
    94: "Improper Control of Generation of Code",
    327: "Use of Broken or Risky Cryptographic Algorithm",
    522: "Insufficiently Protected Credentials",
    611: "Improper Restriction of XML External Entity Reference",
    918: "Server-Side Request Forgery (SSRF)",
    77: "Command Injection",
    119: "Improper Restriction of Operations within Buffer",
}


# Keyword mappings for automated classification
OWASP_KEYWORDS = {
    "A01": ["access control", "authorization", "permission", "privilege", "role", "unauthorized"],
    "A02": ["encryption", "crypto", "password", "hash", "tls", "ssl", "cipher", "key management"],
    "A03": ["injection", "sql", "xss", "command", "ldap", "xpath", "nosql", "script injection"],
    "A04": ["threat model", "design flaw", "architecture", "insecure design", "missing security"],
    "A05": ["configuration", "default", "unnecessary", "misconfigur", "stack trace", "error message"],
    "A06": ["dependency", "library", "component", "outdated", "vulnerable version", "cve"],
    "A07": ["authentication", "session", "credential", "login", "password reset", "mfa", "jwt"],
    "A08": ["serialization", "deserialization", "integrity", "tampering", "unsigned", "ci/cd"],
    "A09": ["logging", "monitoring", "audit", "detection", "alerting", "incident response"],
    "A10": ["ssrf", "server-side request", "url fetch", "internal resource", "metadata"],
}


CWE_KEYWORDS = {
    79: ["xss", "cross-site scripting", "reflected", "stored", "dom-based"],
    89: ["sql injection", "sqli", "database query", "prepared statement"],
    20: ["input validation", "sanitization", "validation", "untrusted input"],
    78: ["command injection", "os command", "shell execution"],
    22: ["path traversal", "directory traversal", "../", "file access"],
    352: ["csrf", "cross-site request forgery", "token", "state-changing"],
    434: ["file upload", "arbitrary upload", "malicious file"],
    306: ["missing authentication", "unauthenticated", "no auth"],
    862: ["missing authorization", "unauthorized access", "access control"],
    798: ["hardcoded", "credentials", "api key", "password in code"],
    287: ["weak authentication", "bypass authentication"],
    327: ["weak crypto", "md5", "sha1", "broken algorithm"],
    918: ["ssrf", "server-side request forgery"],
}


@dataclass
class ComplianceReport:
    """Compliance mapping report."""
    
    owasp_coverage: Dict[str, List[int]] = field(default_factory=dict)  # OWASP code -> vuln IDs
    cwe_coverage: Dict[int, List[int]] = field(default_factory=dict)   # CWE ID -> vuln IDs
    unmapped_vulnerabilities: List[int] = field(default_factory=list)
    
    total_vulnerabilities: int = 0
    mapped_to_owasp: int = 0
    mapped_to_cwe: int = 0


class ComplianceMapper:
    """Map vulnerabilities to compliance standards."""
    
    def __init__(self):
        """Initialize the compliance mapper."""
        pass
    
    def map_vulnerability_to_owasp(self, vuln: Vulnerability) -> List[str]:
        """
        Map a vulnerability to OWASP Top 10 categories using keyword matching.
        
        Args:
            vuln: Vulnerability to map
            
        Returns:
            List of OWASP codes (e.g., ["A01", "A07"])
        """
        matches = []
        
        # Combine title, description, and attack vector for matching
        text = f"{vuln.title} {vuln.description} {vuln.attack_vector}".lower()
        
        for owasp_code, keywords in OWASP_KEYWORDS.items():
            if any(keyword.lower() in text for keyword in keywords):
                matches.append(owasp_code)
        
        return matches
    
    def map_vulnerability_to_cwe(self, vuln: Vulnerability) -> List[int]:
        """
        Map a vulnerability to CWE IDs using keyword matching.
        
        Args:
            vuln: Vulnerability to map
            
        Returns:
            List of CWE IDs (e.g., [79, 89])
        """
        matches = []
        
        text = f"{vuln.title} {vuln.description} {vuln.attack_vector}".lower()
        
        for cwe_id, keywords in CWE_KEYWORDS.items():
            if any(keyword.lower() in text for keyword in keywords):
                matches.append(cwe_id)
        
        return matches
    
    def generate_compliance_report(self, state: CrucibleState) -> ComplianceReport:
        """
        Generate a comprehensive compliance report.
        
        Args:
            state: Current crucible state
            
        Returns:
            ComplianceReport with all mappings
        """
        report = ComplianceReport()
        report.total_vulnerabilities = len(state.vulnerabilities)
        
        mapped_to_owasp = set()
        mapped_to_cwe = set()
        
        for vuln in state.vulnerabilities:
            # Map to OWASP
            owasp_codes = self.map_vulnerability_to_owasp(vuln)
            for code in owasp_codes:
                if code not in report.owasp_coverage:
                    report.owasp_coverage[code] = []
                report.owasp_coverage[code].append(vuln.vulnerability_id)
                mapped_to_owasp.add(vuln.vulnerability_id)
            
            # Map to CWE
            cwe_ids = self.map_vulnerability_to_cwe(vuln)
            for cwe_id in cwe_ids:
                if cwe_id not in report.cwe_coverage:
                    report.cwe_coverage[cwe_id] = []
                report.cwe_coverage[cwe_id].append(vuln.vulnerability_id)
                mapped_to_cwe.add(vuln.vulnerability_id)
            
            # Track unmapped
            if not owasp_codes and not cwe_ids:
                report.unmapped_vulnerabilities.append(vuln.vulnerability_id)
        
        report.mapped_to_owasp = len(mapped_to_owasp)
        report.mapped_to_cwe = len(mapped_to_cwe)
        
        return report
    
    def get_owasp_summary(self, report: ComplianceReport) -> Dict[str, dict]:
        """
        Get OWASP Top 10 summary with counts.
        
        Returns:
            Dict mapping OWASP code to {name, count, vuln_ids}
        """
        summary = {}
        
        for owasp_code, name in OWASP_TOP_10_2021.items():
            vuln_ids = report.owasp_coverage.get(owasp_code, [])
            summary[owasp_code] = {
                "name": name,
                "count": len(vuln_ids),
                "vuln_ids": vuln_ids,
                "tested": len(vuln_ids) > 0,
            }
        
        return summary
    
    def get_cwe_summary(self, report: ComplianceReport) -> List[dict]:
        """
        Get CWE summary sorted by count.
        
        Returns:
            List of dicts with CWE info, sorted by prevalence
        """
        summary = []
        
        for cwe_id, vuln_ids in sorted(report.cwe_coverage.items(), 
                                       key=lambda x: len(x[1]), 
                                       reverse=True):
            summary.append({
                "cwe_id": cwe_id,
                "name": CWE_DATABASE.get(cwe_id, f"CWE-{cwe_id}"),
                "count": len(vuln_ids),
                "vuln_ids": vuln_ids,
            })
        
        return summary
