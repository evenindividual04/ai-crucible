"""Tests for the state module."""

import pytest
from datetime import datetime

from crucible.state import (
    CrucibleState,
    DesignComponent,
    Vulnerability,
    Patch,
    IterationSummary,
)


class TestDesignComponent:
    """Tests for DesignComponent model."""
    
    def test_create_component(self):
        comp = DesignComponent(
            component_id=1,
            name="Test Component",
            responsibility="Do something",
            assumptions=["Assumption 1"],
            dependencies=[],
        )
        assert comp.component_id == 1
        assert comp.name == "Test Component"
        assert len(comp.assumptions) == 1
    
    def test_component_with_dependencies(self):
        comp = DesignComponent(
            component_id=2,
            name="Dependent Component",
            responsibility="Depends on component 1",
            assumptions=["Always works"],
            dependencies=[1],
        )
        assert comp.dependencies == [1]


class TestVulnerability:
    """Tests for Vulnerability model."""
    
    def test_create_vulnerability(self):
        vuln = Vulnerability(
            vulnerability_id=1,
            severity="CRITICAL",
            confidence=0.9,
            domain="SECURITY",
            title="Test Vulnerability",
            description="A test vulnerability",
            attack_vector="Attack vector description",
            affected_components=[1, 2],
            iteration_found=1,
        )
        assert vuln.vulnerability_id == 1
        assert vuln.severity == "CRITICAL"
        assert vuln.confidence == 0.9
        assert vuln.domain == "SECURITY"
    
    def test_vulnerability_timestamp(self):
        vuln = Vulnerability(
            vulnerability_id=1,
            severity="HIGH",
            confidence=0.7,
            domain="SCALABILITY",
            title="Test",
            description="",
            attack_vector="",
            affected_components=[],
            iteration_found=0,
        )
        assert isinstance(vuln.created_at, datetime)


class TestCrucibleState:
    """Tests for CrucibleState model."""
    
    def test_create_initial_state(self):
        state = CrucibleState(
            user_prompt="Design a system",
        )
        assert state.user_prompt == "Design a system"
        assert state.status == "INIT"
        assert state.iteration_count == 0
        assert state.max_iterations == 3
    
    def test_allocate_ids(self):
        state = CrucibleState(user_prompt="Test")
        
        comp_id1 = state.allocate_component_id()
        comp_id2 = state.allocate_component_id()
        assert comp_id1 == 1
        assert comp_id2 == 2
        
        vuln_id = state.allocate_vulnerability_id()
        assert vuln_id == 1
        
        patch_id = state.allocate_patch_id()
        assert patch_id == 1
    
    def test_get_vulnerability_by_id(self, sample_vulnerability):
        state = CrucibleState(user_prompt="Test")
        state.vulnerabilities.append(sample_vulnerability)
        
        found = state.get_vulnerability_by_id(1)
        assert found is not None
        assert found.title == sample_vulnerability.title
        
        not_found = state.get_vulnerability_by_id(999)
        assert not_found is None
    
    def test_get_unpatched_critical_count(self, sample_vulnerability):
        state = CrucibleState(user_prompt="Test")
        state.vulnerabilities.append(sample_vulnerability)
        
        # Initially unpatched
        assert state.get_unpatched_critical_count() == 1
        
        # Add a patch
        patch = Patch(
            patch_id=1,
            target_vulnerability_id=1,
            fix_description="Fixed it",
            design_changes=["Added validation"],
        )
        state.patches.append(patch)
        
        # Now patched
        assert state.get_unpatched_critical_count() == 0
    
    def test_touch_updates_timestamp(self):
        state = CrucibleState(user_prompt="Test")
        old_time = state.last_modified_at
        
        import time
        time.sleep(0.01)  # Small delay
        
        state.touch()
        assert state.last_modified_at > old_time
