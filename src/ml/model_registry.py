"""ML Model Registry for version management."""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

import joblib

logger = logging.getLogger(__name__)

REGISTRY_DIR = Path(__file__).parent / "registry"
REGISTRY_DIR.mkdir(exist_ok=True)


@dataclass
class ModelVersion:
    """Metadata for a model version."""
    model_name: str
    version: str
    created_at: str
    samples_trained: int
    metrics: dict
    file_path: str
    is_active: bool = True


class ModelRegistry:
    """
    Registry for ML model versioning and management.

    Tracks model versions, metrics, and handles model loading.
    """

    def __init__(self, registry_dir: Path = REGISTRY_DIR):
        self.registry_dir = registry_dir
        self.models_dir = registry_dir / "models"
        self.models_dir.mkdir(exist_ok=True)
        self.registry_file = registry_dir / "registry.json"
        self._load_registry()

    def _load_registry(self):
        """Load registry from disk."""
        if self.registry_file.exists():
            with open(self.registry_file, "r") as f:
                self.registry = json.load(f)
        else:
            self.registry = {"models": {}, "active_versions": {}}

    def _save_registry(self):
        """Save registry to disk."""
        with open(self.registry_file, "w") as f:
            json.dump(self.registry, f, indent=2)

    def register_model(
        self,
        model_name: str,
        model: Any,
        samples_trained: int,
        metrics: dict,
    ) -> ModelVersion:
        """
        Register a new model version.

        Args:
            model_name: Name of the model (e.g., "demand_forecaster")
            model: The trained model object
            samples_trained: Number of samples used for training
            metrics: Training/validation metrics

        Returns:
            ModelVersion with registration details
        """
        # Generate version
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version = f"v{timestamp}"

        # Save model
        model_filename = f"{model_name}_{version}.joblib"
        model_path = self.models_dir / model_filename
        joblib.dump(model, model_path)

        # Create version record
        model_version = ModelVersion(
            model_name=model_name,
            version=version,
            created_at=datetime.now().isoformat(),
            samples_trained=samples_trained,
            metrics=metrics,
            file_path=str(model_path),
            is_active=True,
        )

        # Update registry
        if model_name not in self.registry["models"]:
            self.registry["models"][model_name] = []

        self.registry["models"][model_name].append(asdict(model_version))

        # Set as active version
        self.registry["active_versions"][model_name] = version

        self._save_registry()

        logger.info(f"Registered {model_name} version {version}")
        return model_version

    def get_active_model(self, model_name: str) -> Optional[Any]:
        """
        Load the active version of a model.

        Args:
            model_name: Name of the model to load

        Returns:
            Loaded model object or None if not found
        """
        active_version = self.registry["active_versions"].get(model_name)
        if not active_version:
            logger.warning(f"No active version for {model_name}")
            return None

        return self.get_model(model_name, active_version)

    def get_model(self, model_name: str, version: str) -> Optional[Any]:
        """
        Load a specific model version.

        Args:
            model_name: Name of the model
            version: Version string

        Returns:
            Loaded model object or None if not found
        """
        versions = self.registry["models"].get(model_name, [])
        for v in versions:
            if v["version"] == version:
                model_path = Path(v["file_path"])
                if model_path.exists():
                    return joblib.load(model_path)
                else:
                    logger.error(f"Model file not found: {model_path}")
                    return None

        logger.warning(f"Version {version} not found for {model_name}")
        return None

    def set_active_version(self, model_name: str, version: str) -> bool:
        """
        Set the active version for a model.

        Args:
            model_name: Name of the model
            version: Version to activate

        Returns:
            True if successful, False otherwise
        """
        versions = self.registry["models"].get(model_name, [])
        version_exists = any(v["version"] == version for v in versions)

        if not version_exists:
            logger.error(f"Version {version} not found for {model_name}")
            return False

        self.registry["active_versions"][model_name] = version
        self._save_registry()

        logger.info(f"Set {model_name} active version to {version}")
        return True

    def list_versions(self, model_name: str) -> list[ModelVersion]:
        """
        List all versions of a model.

        Args:
            model_name: Name of the model

        Returns:
            List of ModelVersion objects
        """
        versions = self.registry["models"].get(model_name, [])
        return [ModelVersion(**v) for v in versions]

    def get_model_metrics(self, model_name: str, version: Optional[str] = None) -> dict:
        """
        Get metrics for a model version.

        Args:
            model_name: Name of the model
            version: Specific version (defaults to active)

        Returns:
            Metrics dictionary
        """
        if version is None:
            version = self.registry["active_versions"].get(model_name)

        if not version:
            return {}

        versions = self.registry["models"].get(model_name, [])
        for v in versions:
            if v["version"] == version:
                return v.get("metrics", {})

        return {}

    def cleanup_old_versions(self, model_name: str, keep_count: int = 5) -> int:
        """
        Remove old model versions, keeping the most recent.

        Args:
            model_name: Name of the model
            keep_count: Number of versions to keep

        Returns:
            Number of versions removed
        """
        versions = self.registry["models"].get(model_name, [])

        if len(versions) <= keep_count:
            return 0

        # Sort by created_at, oldest first
        sorted_versions = sorted(versions, key=lambda v: v["created_at"])
        to_remove = sorted_versions[:-keep_count]

        removed_count = 0
        for v in to_remove:
            # Don't remove active version
            if v["version"] == self.registry["active_versions"].get(model_name):
                continue

            # Remove model file
            model_path = Path(v["file_path"])
            if model_path.exists():
                model_path.unlink()

            # Remove from registry
            versions.remove(v)
            removed_count += 1

        self._save_registry()
        logger.info(f"Cleaned up {removed_count} old versions of {model_name}")
        return removed_count
