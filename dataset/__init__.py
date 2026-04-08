from dataset.image_base import ImageBaseDataset

IMAGE_DATASETS = {
    "image_base": ImageBaseDataset,
}

VIDEO_DATASETS = {}


def build_dataset(cfg, dataset_name=None):
    """Build dataset instance by modality and dataset_name."""
    registry = IMAGE_DATASETS if cfg.modality == "image" else VIDEO_DATASETS
    cls = registry.get(dataset_name)
    if cls is None:
        raise ValueError(f"Dataset [{dataset_name}] not found under [{cfg.modality}] modality")
    return cls(cfg=cfg)
