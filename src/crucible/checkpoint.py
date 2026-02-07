"""
Checkpoint management for the AI Crucible.

Allows saving and resuming runs from a saved state with iteration-specific checkpoints.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import logging

from crucible.state import CrucibleState

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages saving and loading run checkpoints.
    
    Supports iteration-specific checkpoints and resuming interrupted runs.
    """
    
    def __init__(self, run_id: str, output_dir: Path):
        """
        Initialize checkpoint manager.
        
        Args:
            run_id: Unique identifier for this run
            output_dir: Base directory for outputs
        """
        self.run_id = run_id
        self.output_dir = output_dir
        self.checkpoint_dir = output_dir / run_id / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def save(
        self, 
        state: CrucibleState, 
        iteration: int,
        path: Optional[Path] = None,
        metadata: Optional[dict] = None
    ) -> Path:
        """
        Save a checkpoint for the current iteration.
        
        Args:
            state: Current crucible state
            iteration: Current iteration number
            path: Optional specific path (overrides default)
            metadata: Optional additional metadata to save
            
        Returns:
            Path to saved checkpoint file
        """
        if path is None:
            checkpoint_file = self.checkpoint_dir / f"iter_{iteration}.json"
        else:
            checkpoint_file = path
        
        # Serialize state
        state_dict = state.model_dump(mode="json")
        
        checkpoint_data = {
            "version": 2,  # Updated version
            "run_id": self.run_id,
            "iteration": iteration,
            "saved_at": datetime.utcnow().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "state": state_dict,
            "status": state.status,
            "summary": {
                "total_vulnerabilities": len(state.vulnerabilities),
                "total_patches": len(state.patches),
                "active_vulnerabilities": len(state.active_vulnerabilities),
                "active_agents": state.active_agents,
            },
            "metadata": metadata or {}
        }
        
        # Save iteration-specific checkpoint
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2, default=str)
        
        # Also save as "latest" for quick resume
        latest_file = self.checkpoint_dir / "latest.json"
        with open(latest_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2, default=str)
        
        logger.info(f"Checkpoint saved to: {checkpoint_file}")
        
        return checkpoint_file
    
    def load(
        self, 
        iteration: Optional[int] = None,
        path: Optional[Path] = None
    ) -> tuple[CrucibleState, dict]:
        """
        Load a checkpoint.
        
        Args:
            iteration: Specific iteration to load, or None for latest
            path: Optional specific path to load from
            
        Returns:
            (CrucibleState, checkpoint_data) tuple
            
        Raises:
            FileNotFoundError: If checkpoint doesn't exist
        """
        if path is not None:
            checkpoint_file = path
        elif iteration is None:
            checkpoint_file = self.checkpoint_dir / "latest.json"
        else:
            checkpoint_file = self.checkpoint_dir / f"iter_{iteration}.json"
        
        if not checkpoint_file.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_file}")
        
        with open(checkpoint_file) as f:
            data = json.load(f)
        
        # Validate version
        version = data.get("version", 1)
        if version not in [1, 2]:
            raise ValueError(f"Unsupported checkpoint version: {version}")
        
        # Reconstruct state
        state = CrucibleState(**data["state"])
        
        logger.info(f"Checkpoint loaded from: {checkpoint_file}")
        logger.info(f"Resuming from iteration {state.iteration_count}, status: {state.status}")
        
        return state, data
    
    def list_checkpoints(self) -> List[dict]:
        """
        List all available checkpoints for this run.
        
        Returns:
            List of checkpoint metadata dictionaries
        """
        checkpoints = []
        
        for cp_file in sorted(self.checkpoint_dir.glob("iter_*.json")):
            try:
                with open(cp_file) as f:
                    data = json.load(f)
                    checkpoints.append({
                        "iteration": data.get("iteration", 0),
                        "timestamp": data.get("timestamp", data.get("saved_at", "")),
                        "status": data.get("status", "UNKNOWN"),
                        "summary": data.get("summary", {}),
                        "file": str(cp_file)
                    })
            except Exception as e:
                logger.warning(f"Failed to read checkpoint {cp_file}: {e}")
                continue
        
        return checkpoints
    
    def delete_checkpoint(self, iteration: int) -> bool:
        """Delete a specific checkpoint."""
        checkpoint_file = self.checkpoint_dir / f"iter_{iteration}.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            logger.info(f"Deleted checkpoint for iteration {iteration}")
            return True
        return False
    
    def cleanup_old_checkpoints(self, keep_last_n: int = 5) -> int:
        """Delete old checkpoints, keeping only the most recent N."""
        checkpoints = self.list_checkpoints()
        
        if len(checkpoints) <= keep_last_n:
            return 0
        
        to_delete = checkpoints[:-keep_last_n]
        deleted_count = 0
        
        for cp in to_delete:
            iteration = cp["iteration"]
            if self.delete_checkpoint(iteration):
                deleted_count += 1
        
        return deleted_count
    
    def get_latest_iteration(self) -> Optional[int]:
        """Get the iteration number of the most recent checkpoint."""
        checkpoints = self.list_checkpoints()
        if not checkpoints:
            return None
        return checkpoints[-1]["iteration"]
    
    def auto_save(self, state: CrucibleState) -> Optional[Path]:
        """Auto-save checkpoint after each iteration."""
        return self.save(state, state.iteration_count)


def list_all_runs(output_dir: Path) -> List[dict]:
    """List all runs with checkpoints in the output directory."""
    runs = []
    
    if not output_dir.exists():
        return runs
    
    for run_dir in output_dir.iterdir():
        if not run_dir.is_dir():
            continue
        
        checkpoint_dir = run_dir / "checkpoints"
        if not checkpoint_dir.exists():
            continue
        
        latest_file = checkpoint_dir / "latest.json"
        if latest_file.exists():
            try:
                with open(latest_file) as f:
                    data = json.load(f)
                    runs.append({
                        "run_id": run_dir.name,
                        "latest_iteration": data.get("iteration", 0),
                        "timestamp": data.get("timestamp", data.get("saved_at", "")),
                        "status": data.get("status", "UNKNOWN"),
                        "summary": data.get("summary", {})
                    })
            except Exception:
                continue
    
    return sorted(runs, key=lambda r: r.get("timestamp", ""), reverse=True)


# Legacy support
def save_checkpoint(state: CrucibleState, path: Path) -> Path:
    """Convenience function to save a checkpoint (legacy API)."""
    mgr = CheckpointManager(
        run_id=getattr(state, 'run_id', 'default'),
        output_dir=path.parent
    )
    return mgr.save(state, state.iteration_count, path=path)


def load_checkpoint(path: Path) -> CrucibleState:
    """Convenience function to load a checkpoint (legacy API)."""
    mgr = CheckpointManager(
        run_id='default',
        output_dir=path.parent
    )
    state, _ = mgr.load(path=path)
    return state
