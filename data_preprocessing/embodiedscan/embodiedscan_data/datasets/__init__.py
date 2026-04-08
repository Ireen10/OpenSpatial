from typing import Dict, Type

from embodiedscan_data.datasets.base import DatasetConfig

REGISTRY: Dict[str, Type[DatasetConfig]] = {}

ALL_DATASETS = ["scannet", "3rscan", "matterport3d", "arkitscenes"]


def register(cls: Type[DatasetConfig]) -> Type[DatasetConfig]:
    """Decorator to register a DatasetConfig subclass."""
    REGISTRY[cls.name] = cls
    return cls


def get_dataset_config(name: str) -> DatasetConfig:
    """Instantiate and return a DatasetConfig by name."""
    if name not in REGISTRY:
        raise ValueError(f"Unknown dataset: {name}. Available: {list(REGISTRY.keys())}")
    return REGISTRY[name]()
