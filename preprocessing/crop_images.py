"""Crop images and generate txt paths file for feature extraction using bottom-up"""
import os
import pickle


from tqdm import tqdm

from filter_eval_set import get_local_fiftyone_image_path
from utils.utils import (
    crop_image_to_bounding_box_size,
    get_path_of_cropped_image, IMGS_CROPPED_BASE_PATH, get_path_of_image,
)
import argparse
from PIL import Image as PIL_Image


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", type=str, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    arg_values = get_args()

    eval_sets = pickle.load(open(arg_values.eval_set, "rb"))

    img_paths = []

    img_cropped_paths = []
    os.makedirs(IMGS_CROPPED_BASE_PATH, exist_ok=True)

    for key, set in eval_sets.items():
        print(key)
        for sample in tqdm(set):
            fiftyone_img_example_path = get_local_fiftyone_image_path(sample["img_example"])
            fiftyone_img_counterexample_path = get_local_fiftyone_image_path(sample["img_counterexample"])

            img_example = PIL_Image.open(fiftyone_img_example_path)
            img_example_local_path = get_path_of_image(fiftyone_img_example_path)
            img_example.save(img_example_local_path)
            img_paths.append(img_example_local_path)

            img_counterexample = PIL_Image.open(fiftyone_img_counterexample_path)
            img_counterexample_local_path = get_path_of_image(fiftyone_img_counterexample_path)
            img_counterexample.save(img_counterexample_local_path)
            img_paths.append(img_counterexample_local_path)

            img_example_cropped = crop_image_to_bounding_box_size(
                img_example_local_path,
                sample["relationship_target"]["bounding_box"],
                return_numpy_array=False,
            )
            path_example_cropped = get_path_of_cropped_image(
                sample["img_example"], sample["relationship_target"]
            )
            img_example_cropped.save(path_example_cropped)
            img_counterexample_cropped = crop_image_to_bounding_box_size(
                img_counterexample_local_path,
                sample["counterexample_relationship_target"]["bounding_box"],
                return_numpy_array=False,
            )
            path_counterexample_cropped = get_path_of_cropped_image(
                sample["img_counterexample"], sample["counterexample_relationship_target"]
            )
            img_counterexample_cropped.save(path_counterexample_cropped)
            img_cropped_paths.append(path_example_cropped)
            img_cropped_paths.append(path_counterexample_cropped)

    out_file_name = (
        "img_paths_" + os.path.basename(arg_values.eval_set.split(".p")[0]) + ".txt"
    )
    with open(os.path.join("preprocessing", out_file_name), "w") as text_file:
        for path in {p for p in img_paths}:
            text_file.write(path + "\n")

    out_file_cropped_name = (
            "img_cropped_paths_" + os.path.basename(arg_values.eval_set.split(".p")[0]) + ".txt"
    )
    with open(os.path.join("preprocessing", out_file_cropped_name), "w") as text_file:
        for path in {p for p in img_cropped_paths}:
            text_file.write(path + "\n")
