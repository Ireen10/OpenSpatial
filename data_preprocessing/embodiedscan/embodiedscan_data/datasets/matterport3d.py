import os
from typing import List, Optional

import numpy as np

from embodiedscan_data.datasets import register
from embodiedscan_data.datasets.base import DatasetConfig


@register
class Matterport3DConfig(DatasetConfig):
    name = "matterport3d"
    dataset_key = "matterport3d"
    depth_scale = 4000
    ann_files = [
        "data/embodiedscan_infos_train.pkl",
        "data/embodiedscan_infos_val.pkl",
        "data/embodiedscan_infos_test.pkl",
    ]

    def list_scenes(self, data_root: str) -> List[str]:
        mp3d_dir = os.path.join(data_root, "matterport3d")
        if not os.path.isdir(mp3d_dir):
            return []
        scenes = []
        for building_id in sorted(os.listdir(mp3d_dir)):
            building_dir = os.path.join(mp3d_dir, building_id)
            if not os.path.isdir(building_dir):
                continue
            region_dir = os.path.join(building_dir, "region_segmentations")
            if not os.path.isdir(region_dir):
                continue
            for f in sorted(os.listdir(region_dir)):
                if f.endswith(".ply"):
                    region_name = f.split(".")[0]
                    scenes.append(f"matterport3d/{building_id}/{region_name}")
        return scenes

    def list_cameras(self, data_root: str, scene: str) -> List[str]:
        parts = scene.split("/")
        building_id = parts[1]
        color_dir = os.path.join(data_root, "matterport3d", building_id, "matterport_color_images")
        if not os.path.isdir(color_dir):
            return []
        cameras = []
        for f in sorted(os.listdir(color_dir)):
            if not f.endswith(".jpg"):
                continue
            prefix = f[:-8]
            suffix = f[-7:-4]
            cameras.append(prefix + suffix)
        return cameras

    def get_scene_id(self, scene: str) -> str:
        parts = scene.split("/")
        return f"{parts[1]}__{parts[2]}"

    def get_intrinsic(self, data_root: str, scene: str, camera: str) -> str:
        parts = scene.split("/")
        building_id = parts[1]
        suffix = camera[-3:]
        prefix = camera[:-3]
        intrinsic_filename = f"{prefix}intrinsics_{suffix[0]}.txt"
        intrinsic_path = os.path.join(
            data_root, "matterport3d", building_id, "matterport_camera_intrinsics", intrinsic_filename
        )
        output_path = intrinsic_path.replace(".txt", "_matrix.txt")
        if not os.path.exists(output_path):
            self._parse_intrinsic(intrinsic_path, output_path)
        return os.path.relpath(output_path, data_root)

    def _parse_intrinsic(self, intrinsic_path: str, output_path: str) -> None:
        with open(intrinsic_path, "r") as f:
            values = [float(x) for x in f.read().split()]
        fx, fy, cx, cy = values[2], values[3], values[4], values[5]
        matrix = np.array([[fx, 0, cx, 0], [0, fy, cy, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        with open(output_path, "w") as f:
            for row in matrix:
                f.write(" ".join(f"{v:.6f}" for v in row) + "\n")

    def get_depth_map(self, data_root: str, scene: str, camera: str) -> Optional[str]:
        parts = scene.split("/")
        building_id = parts[1]
        suffix = camera[-3:]
        prefix = camera[:-3]
        return os.path.join("matterport3d", building_id, "matterport_depth_images", f"{prefix}d{suffix}.png")

    def skip_scene(self, data_root: str, scene: str) -> bool:
        parts = scene.split("/")
        building_id = parts[1]
        bd = os.path.join(data_root, "matterport3d", building_id)
        return (not os.path.isdir(os.path.join(bd, "region_segmentations"))
                or not os.path.isdir(os.path.join(bd, "matterport_color_images")))

    def skip_camera(self, data_root: str, scene: str, camera: str) -> bool:
        parts = scene.split("/")
        building_id = parts[1]
        suffix = camera[-3:]
        prefix = camera[:-3]
        intrinsic = os.path.join(data_root, "matterport3d", building_id,
                                  "matterport_camera_intrinsics", f"{prefix}intrinsics_{suffix[0]}.txt")
        depth = os.path.join(data_root, "matterport3d", building_id,
                              "matterport_depth_images", f"{prefix}d{suffix}.png")
        return not os.path.exists(intrinsic) or not os.path.exists(depth)
