import logging
import os
from typing import List

import numpy as np

from embodiedscan_data.datasets import register
from embodiedscan_data.datasets.base import DatasetConfig

logger = logging.getLogger(__name__)


@register
class RScan3DConfig(DatasetConfig):
    name = "3rscan"
    dataset_key = "3rscan"
    depth_scale = 1000
    ann_files = [
        "data/embodiedscan_infos_train.pkl",
        "data/embodiedscan_infos_val.pkl",
        "data/embodiedscan_infos_test.pkl",
    ]

    def list_scenes(self, data_root: str) -> List[str]:
        rscan_dir = os.path.join(data_root, "3rscan")
        if not os.path.isdir(rscan_dir):
            return []
        return sorted(
            f"3rscan/{d}" for d in os.listdir(rscan_dir)
            if os.path.isdir(os.path.join(rscan_dir, d))
        )

    def list_cameras(self, data_root: str, scene: str) -> List[str]:
        scene_name = scene.split("/")[-1]
        seq_dir = os.path.join(data_root, "3rscan", scene_name, "sequence")
        if not os.path.isdir(seq_dir):
            return []
        return sorted(f.split(".")[0] for f in os.listdir(seq_dir) if f.endswith(".jpg"))

    def get_scene_id(self, scene: str) -> str:
        return scene.split("/")[-1]

    def get_intrinsic(self, data_root: str, scene: str, camera: str) -> str:
        scene_name = scene.split("/")[-1]
        info_path = os.path.join(data_root, "3rscan", scene_name, "sequence", "_info.txt")
        output_path = os.path.join(data_root, "3rscan", scene_name, "sequence", "_depth_intrinsic.txt")
        if not os.path.exists(output_path):
            self._extract_intrinsic(info_path, output_path)
        return os.path.relpath(output_path, data_root)

    def _extract_intrinsic(self, info_path: str, output_path: str) -> None:
        with open(info_path, "r") as f:
            content = f.read()
        for line in content.split("\n"):
            if line.startswith("m_calibrationDepthIntrinsic"):
                values_str = line.split("=", 1)[1].strip()
                values = [float(x) for x in values_str.split()]
                matrix = np.array(values).reshape(4, 4)
                with open(output_path, "w") as f:
                    for row in matrix:
                        f.write(" ".join(f"{v:.6f}" for v in row) + "\n")
                return
        logger.warning("No m_calibrationDepthIntrinsic found in %s", info_path)

    def skip_scene(self, data_root: str, scene: str) -> bool:
        scene_name = scene.split("/")[-1]
        seq_dir = os.path.join(data_root, "3rscan", scene_name, "sequence")
        if not os.path.isdir(seq_dir):
            return True
        info_path = os.path.join(seq_dir, "_info.txt")
        if not os.path.exists(info_path):
            return True
        with open(info_path, "r") as f:
            return "m_calibrationDepthIntrinsic" not in f.read()
