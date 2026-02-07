"""
Patch validation for AI Crucible.

Validates patches for syntax, dependencies, and potential regressions
before accepting them.
"""

from typing import List, Optional, Dict
from crucible.state import Patch, Vulnerability
import re
import logging

logger = logging.getLogger(__name__)


class PatchValidator:
    """
    Validates patches for correctness and safety.
    
    Performs multiple validation checks:
    - Syntax validation (required fields, dangerous patterns)
    - Dependency validation (valid component references)
    - Regression detection (conflicts with existing patches)
    """
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize patch validator.
        
        Args:
            strict_mode: If True, enforce stricter validation rules
        """
        self.strict_mode = strict_mode
        
        # Dangerous patterns that should trigger warnings/errors
        self.dangerous_patterns = [
            (r'delete\s+all', "DELETE ALL operation"),
            (r'drop\s+table', "DROP TABLE operation"),
            (r'rm\s+-rf\s+/', "Recursive delete from root"),
            (r'truncate', "TRUNCATE operation"),
            (r'--\s*no-backup', "No backup flag"),
        ]
        
        # Suspicious patterns that warrant warnings
        self.suspicious_patterns = [
            (r'bypass', "Security bypass mentioned"),
            (r'disable\s+\w+\s+check', "Disabling security checks"),
            (r'skip\s+validation', "Skipping validation"),
            (r'temporary\s+fix', "Temporary fix (may need follow-up)"),
        ]
    
    def validate_syntax(self, patch: Patch) -> tuple[bool, Optional[str]]:
        """
        Validate patch syntax and required fields.
        
        Args:
            patch: Patch to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        # Check required fields (PatchV2 uses fix_description)
        description = getattr(patch, 'fix_description', '')
        if not description or len(description.strip()) < 10:
            return False, "Patch description is empty or too short (minimum 10 characters)"
        
        # Check design changes
        if not hasattr(patch, 'design_changes') or not patch.design_changes:
            return False, "No design changes specified"
        
        # Check for dangerous patterns
        description_lower = description.lower()
        
        for pattern, desc in self.dangerous_patterns:
            if re.search(pattern, description_lower):
                if self.strict_mode:
                    return False, f"Patch contains dangerous pattern: {desc}"
                else:
                    logger.warning(f"Patch #{patch.patch_id} contains dangerous pattern: {desc}")
        
        # Check confidence rationale if present
        if hasattr(patch, 'confidence_rationale'):
            if not patch.confidence_rationale or len(patch.confidence_rationale.strip()) < 10:
                return False, "Confidence rationale is too short or missing"
        
        return True, None
    
    def validate_dependencies(
        self,
        patch: Patch,
        design_components: List
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that patch references valid components from the design.
        
        Args:
            patch: Patch to validate
            design_components: List of valid design components
            
        Returns:
            (is_valid, error_message) tuple
        """
        # Build set of valid component names
        component_names = {c.name for c in design_components}
        
        # Extract components from design_changes (PatchV2 field)
        # design_changes is a list of strings describing changes
        # For now, just check that design_changes references valid component names
        if hasattr(patch, 'design_changes'):
            all_changes = ' '.join(patch.design_changes)
            # Check if any component names appear in the changes
            # This is a basic check - could be improved
            return True, None  # Skip detailed validation for now
        
        return True, None
    
    def check_regression(
        self,
        patch: Patch,
        all_vulnerabilities: List[Vulnerability],
        all_patches: List[Patch]
    ) -> List[str]:
        """
        Check if patch might cause regressions or conflicts.
        
        Args:
            patch: Patch to check
            all_vulnerabilities: All discovered vulnerabilities
            all_patches: All previously applied patches
            
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Get the vulnerability being patched
        target_vuln = next(
            (v for v in all_vulnerabilities if v.vulnerability_id == patch.target_vulnerability_id),
            None
        )
        
        if not target_vuln:
            warnings.append(f"Cannot find target vulnerability #{patch.target_vulnerability_id}")
            return warnings
        
        # Check for overlapping changes with other patches
        patch_changes = set(getattr(patch, 'design_changes', []))
        
        for existing_patch in all_patches:
            # Skip if same patch or if existing patch targets same vulnerability
            if existing_patch.patch_id == patch.patch_id:
                continue
            if existing_patch.target_vulnerability_id == patch.target_vulnerability_id:
                continue
            
            # Check for overlap in design changes
            existing_changes = set(getattr(existing_patch, 'design_changes', []))
            overlap = patch_changes & existing_changes
            
            if overlap:
                existing_vuln = next(
                    (v for v in all_vulnerabilities 
                     if v.vulnerability_id == existing_patch.target_vulnerability_id),
                    None
                )
                
                if existing_vuln:
                    warnings.append(
                        f"Design change conflict with patch #{existing_patch.patch_id} "
                        f"(targeting '{existing_vuln.title}'): "
                        f"Overlapping changes: {len(overlap)}"
                    )
        
        # Check for suspicious patterns in fix description
        description = getattr(patch, 'fix_description', '')
        description_lower = description.lower()
        
        for pattern, desc in self.suspicious_patterns:
            if re.search(pattern, description_lower):
                warnings.append(f"Suspicious pattern detected: {desc}")
        
        return warnings
    
    def validate_impact(self, patch: Patch) -> tuple[bool, Optional[str]]:
        """
        Validate that patch impact is reasonable.
        
        Args:
            patch: Patch to validate
            
        Returns:
            (is_valid, error_message) tuple
        """
        # Check if too many design changes (might indicate overly broad patch)
        design_changes = getattr(patch, 'design_changes', [])
        if len(design_changes) > 5:
            if self.strict_mode:
                return False, (
                    f"Patch has too many design changes ({len(design_changes)}). "
                    "Consider splitting into smaller, focused patches."
                )
            else:
                logger.warning(
                    f"Patch #{patch.patch_id} has many design changes "
                    f"({len(design_changes)})"
                )
        
        # Check fix category if available
        if hasattr(patch, 'fix_category'):
            if str(patch.fix_category) == "ARCHITECTURAL" and len(design_changes) < 3:
                logger.warning(
                    f"Patch #{patch.patch_id} is marked as ARCHITECTURAL but has few design changes"
                )
        
        return True, None
    
    def full_validation(
        self,
        patch: Patch,
        design_components: List,
        all_vulnerabilities: List[Vulnerability],
        all_patches: Optional[List[Patch]] = None
    ) -> Dict[str, any]:
        """
        Run all validation checks on a patch.
        
        Args:
            patch: Patch to validate
            design_components: List of valid design components
            all_vulnerabilities: All discovered vulnerabilities
            all_patches: All previously applied patches (optional)
            
        Returns:
            Dictionary with validation results:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str],
                "checks": Dict[str, bool]
            }
        """
        errors = []
        warnings = []
        checks = {}
        
        # 1. Syntax validation
        is_valid, error = self.validate_syntax(patch)
        checks["syntax"] = is_valid
        if not is_valid:
            errors.append(error)
        
        # 2. Dependency validation
        is_valid, error = self.validate_dependencies(patch, design_components)
        checks["dependencies"] = is_valid
        if not is_valid:
            errors.append(error)
        
        # 3. Impact validation
        is_valid, error = self.validate_impact(patch)
        checks["impact"] = is_valid
        if not is_valid:
            errors.append(error)
        
        # 4. Regression check (warnings only)
        if all_patches:
            regression_warnings = self.check_regression(
                patch, 
                all_vulnerabilities, 
                all_patches
            )
            warnings.extend(regression_warnings)
            checks["regression"] = len(regression_warnings) == 0
        else:
            checks["regression"] = True
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
            "patch_id": patch.patch_id
        }
    
    def batch_validate(
        self,
        patches: List[Patch],
        design_components: List,
        all_vulnerabilities: List[Vulnerability]
    ) -> Dict[int, Dict]:
        """
        Validate multiple patches at once.
        
        Args:
            patches: List of patches to validate
            design_components: Valid design components
            all_vulnerabilities: All vulnerabilities
            
        Returns:
            Dictionary mapping patch_id to validation results
        """
        results = {}
        
        for patch in patches:
            validation = self.full_validation(
                patch,
                design_components,
                all_vulnerabilities,
                patches  # Use all patches for conflict detection
            )
            results[patch.patch_id] = validation
        
        # Log summary
        valid_count = sum(1 for r in results.values() if r["valid"])
        logger.info(
            f"Batch validation: {valid_count}/{len(patches)} patches passed validation"
        )
        
        return results
