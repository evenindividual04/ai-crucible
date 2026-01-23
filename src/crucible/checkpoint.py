"""
Checkpoint management for the AI Crucible.

Allows saving and resuming runs from a saved state.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

from crucible.state import CrucibleState

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages saving and loading Crucible state checkpoints."""
    
    def __init__(self, checkpoint_path: Optional[Path] = None):
        self.checkpoint_path = checkpoint_path
    
    def save(self, state: CrucibleState, path: Optional[Path] = None) -> Path:
        """
        Save the current state to a checkpoint file.
        
        Returns the path where the checkpoint was saved.
        """
        save_path = path or self.checkpoint_path
        if save_path is None:
            # Generate a default path
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            save_path = Path(f"crucible_checkpoint_{timestamp}.json")
        
        # Serialize state to JSON
        state_dict = state.model_dump(mode="json")
        
        # Add checkpoint metadata
        checkpoint_data = {
            "version": 1,
            "saved_at": datetime.utcnow().isoformat(),
            "state": state_dict,
        }
        
        save_path.write_text(json.dumps(checkpoint_data, indent=2, default=str))
        logger.info(f"Checkpoint saved to: {save_path}")
        
        return save_path
    
    def load(self, path: Optional[Path] = None) -> CrucibleState:
        """
        Load a state from a checkpoint file.
        
        Returns the restored CrucibleState.
        """
        load_path = path or self.checkpoint_path
        if load_path is None:
            raise ValueError("No checkpoint path specified")
        
        if not load_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {load_path}")
        
        checkpoint_data = json.loads(load_path.read_text())
        
        # Validate version
        version = checkpoint_data.get("version", 0)
        if version != 1:
            raise ValueError(f"Unsupported checkpoint version: {version}")
        
        # Restore state
        state_dict = checkpoint_data["state"]
        state = CrucibleState(**state_dict)
        
        logger.info(f"Checkpoint loaded from: {load_path}")
        logger.info(f"Resuming from iteration {state.iteration_count}, status: {state.status}")
        
        return state
    
    def auto_save(self, state: CrucibleState) -> Optional[Path]:
        """
        Auto-save checkpoint after each iteration.
        
        Only saves if a checkpoint path is configured.
        """
        if self.checkpoint_path is None:
            return None
        
        return self.save(state, self.checkpoint_path)


def save_checkpoint(state: CrucibleState, path: Path) -> Path:
    """Convenience function to save a checkpoint."""
    return CheckpointManager().save(state, path)


def load_checkpoint(path: Path) -> CrucibleState:
    """Convenience function to load a checkpoint."""
    return CheckpointManager().load(path)
