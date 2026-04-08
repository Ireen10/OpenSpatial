from typing import List, Dict, Any
import pandas as pd
from tqdm import tqdm

class SampleGrouper:
    """
        Group single-image samples (attributes as single values) into multi-image samples (attributes as lists).
    """
    def __init__(self, args):
        self.args = args
        self.group_key = self.args.get("group_by", None)
        if self.group_key is None:
            raise ValueError("group_key must be provided for grouping.")
        
        default_group_col_list = ['image', 'id','obj_tags', 'depth_map', 'pose', 'intrinsic', "bboxes_3d_world_coords", 'masks', 'bboxes_2d', "axis_align_matrix", "depth_scale"]
        self.group_col_list = self.args.get("group_col_list", default_group_col_list)
        assert self.group_key not in self.group_col_list, f"group_by '{self.group_key}' must not be in group_col_list {self.group_col_list}"  


    def group(self, dataset: pd.DataFrame) -> pd.DataFrame:
        grouped_examples = dict()

        for idx in tqdm(range(len(dataset)), desc="Grouping samples"):
            sample = dataset.iloc[idx]
            group_value = sample.get(self.group_key, None)
            if group_value is None:
                raise ValueError(f"Sample at index {idx} is missing the group key '{self.group_key}'.")

            if group_value not in grouped_examples:
                grouped_examples[group_value] = {self.group_key: group_value}
                for col in sample.index:
                    if col not in self.group_col_list and col != self.group_key:
                        grouped_examples[group_value][col] = sample.get(col, None)
                    elif col in self.group_col_list:
                        grouped_examples[group_value][col] = []

            for col in self.group_col_list:
                grouped_examples[group_value][col].append(sample.get(col, None))

        grouped_dataset = pd.DataFrame.from_dict(grouped_examples, orient="index")
        grouped_dataset = grouped_dataset.reset_index(drop=True)

        return grouped_dataset

    def run(self, dataset: pd.DataFrame) -> pd.DataFrame:
        """
        Process the dataset to flatten multi-image samples.
        :param dataset: input dataset (pandas.DataFrame)
        :return: flattened dataset (pandas.DataFrame)
        """
        return self.group(dataset)
