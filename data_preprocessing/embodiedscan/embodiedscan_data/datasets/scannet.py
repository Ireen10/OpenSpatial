import os
from typing import List

from embodiedscan_data.datasets import register
from embodiedscan_data.datasets.base import DatasetConfig


@register
class ScanNetConfig(DatasetConfig):
    name = "scannet"
    dataset_key = "scannet"
    depth_scale = 1000
    ann_files = [
        "data/embodiedscan_infos_train.pkl",
        "data/embodiedscan_infos_val.pkl",
        "data/embodiedscan_infos_test.pkl",
    ]

    def list_scenes(self, data_root: str) -> List[str]:
        posed_dir = os.path.join(data_root, "scannet", "posed_images")
        if not os.path.isdir(posed_dir):
            return []
        return sorted(
            f"scannet/{d}" for d in os.listdir(posed_dir)
            if os.path.isdir(os.path.join(posed_dir, d))
        )

    def list_cameras(self, data_root: str, scene: str) -> List[str]:
        scene_name = scene.split("/")[-1]
        scene_dir = os.path.join(data_root, "scannet", "posed_images", scene_name)
        if not os.path.isdir(scene_dir):
            return []
        return sorted(f.split(".")[0] for f in os.listdir(scene_dir) if f.endswith(".jpg"))

    def get_scene_id(self, scene: str) -> str:
        return scene.split("/")[-1]

    def get_intrinsic(self, data_root: str, scene: str, camera: str) -> str:
        scene_name = scene.split("/")[-1]
        return os.path.join("scannet", "scans", scene_name, "intrinsic", "intrinsic_depth.txt")

    def post_process(self, info: dict, data_root: str, scene: str, camera: str) -> dict:
        from PIL import Image
        image_path = info.get("image")
        depth_path = info.get("depth_map")
        if not image_path or not depth_path:
            return info
        abs_image = os.path.join(data_root, image_path) if not os.path.isabs(image_path) else image_path
        abs_depth = os.path.join(data_root, depth_path) if not os.path.isabs(depth_path) else depth_path
        if os.path.exists(abs_image) and os.path.exists(abs_depth):
            img = Image.open(abs_image)
            depth = Image.open(abs_depth)
            if img.size != depth.size:
                img = img.resize(depth.size)
                resized_path = abs_image.replace(".jpg", "_resized.jpg")
                img.save(resized_path)
                info["image"] = os.path.relpath(resized_path, data_root)
        return info

    def skip_scene(self, data_root: str, scene: str) -> bool:
        scene_name = scene.split("/")[-1]
        intrinsic_path = os.path.join(data_root, "scannet", "scans", scene_name, "intrinsic", "intrinsic_depth.txt")
        return not os.path.exists(intrinsic_path)

    def get_save_path(self, data_root: str, scene: str) -> str:
        scene_name = scene.split("/")[-1]
        return os.path.join(data_root, "scannet", "posed_images", scene_name)
