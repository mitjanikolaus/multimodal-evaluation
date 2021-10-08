import argparse
import pickle

from fiftyone import ViewField as F
import fiftyone.zoo as foz
import numpy as np

import matplotlib.pyplot as plt
from PIL import Image as PIL_Image, ImageFilter, ImageStat
from matplotlib.patches import Rectangle
from tqdm import tqdm

from utils import SYNONYMS, NOUN_TUPLES, ATTRIBUTE_TUPLES

# Threshold for overlap of 2 bounding boxes
THRESHOLD_SAME_BOUNDING_BOX = 0.02

# Bounding boxes of objects should be at least 10% of image in width and height
THRESHOLD_MIN_BOUNDING_BOX_WIDTH = 0.1
THRESHOLD_MIN_BOUNDING_BOX_HEIGHT = 0.1

# Bounding box sharpness quotient (relative to whole image)
THRESHOLD_MIN_BOUNDING_BOX_SHARPNESS = 0.6


def get_bounding_box_size(relationship):
    bb = relationship.bounding_box
    size = bb[2] * bb[3]
    return size


def drop_synonyms(relationships, label_name):
    filtered_rels = []
    for relationship in relationships:
        label = relationship[label_name]
        label_exists = False
        for existing_rel in filtered_rels:
            if label in SYNONYMS[existing_rel[label_name]]:
                label_exists = True
                # replace existing rel if new one is bigger
                if get_bounding_box_size(relationship) > get_bounding_box_size(
                    existing_rel
                ):
                    filtered_rels.remove(existing_rel)
                    filtered_rels.append(relationship)
                break
        if not label_exists:
            filtered_rels.append(relationship)

    return filtered_rels


def get_sum_of_bounding_box_sizes(sample):
    return (
        get_bounding_box_size(sample["relationship_target"])
        + get_bounding_box_size(sample["relationship_visual_distractor"])
        + get_bounding_box_size(sample["counterexample_relationship_target"])
        + get_bounding_box_size(sample["counterexample_relationship_visual_distractor"])
    )


def get_image_sharpness(img_data):
    image_filtered = img_data.convert("L")
    image_filtered = image_filtered.filter(ImageFilter.FIND_EDGES)

    variance_of_laplacian = ImageStat.Stat(image_filtered).var
    return variance_of_laplacian[0]


def get_sharpness_quotient_of_bounding_box(img_data, bb):
    cropped = img_data.crop(
        (
            bb[0] * img_data.width,
            bb[1] * img_data.height,
            bb[2] * img_data.width + bb[0] * img_data.width,
            bb[3] * img_data.height + bb[1] * img_data.height,
        )
    )
    sharpness_quotient = get_image_sharpness(cropped) / get_image_sharpness(img_data)
    return sharpness_quotient


def relationship_is_sharp(sample, relationship):
    img_data = PIL_Image.open(sample.filepath)
    sharpness_quotient = get_sharpness_quotient_of_bounding_box(
        img_data, relationship.bounding_box
    )
    return sharpness_quotient > THRESHOLD_MIN_BOUNDING_BOX_SHARPNESS


def show_image_pair(
    image_1_path,
    image_2_path,
    regions_and_attributes_1=None,
    regions_and_attributes_2=None,
):
    fig = plt.gcf()
    fig.set_size_inches(18.5, 10.5)
    img_1_data = PIL_Image.open(image_1_path)
    img_2_data = PIL_Image.open(image_2_path)

    # Transform both images to grayscale if one of them has only one channel
    if img_1_data.mode == "L" or img_2_data.mode == "L":
        img_1_data = img_1_data.convert("L")
        img_2_data = img_2_data.convert("L")

    # Make images equal size:
    if img_2_data.height > img_1_data.height:
        img_1_data_adjusted = img_1_data.crop(
            (0, 0, img_1_data.width, img_2_data.height)
        )
        img_2_data_adjusted = img_2_data
    else:
        img_1_data_adjusted = img_1_data
        img_2_data_adjusted = img_2_data.crop(
            (0, 0, img_2_data.width, img_1_data.height)
        )

    image = np.column_stack((img_1_data_adjusted, img_2_data_adjusted))

    plt.imshow(image)

    colors = ["green", "red"]
    ax = plt.gca()
    if regions_and_attributes_1:
        for relationship, color in zip(regions_and_attributes_1, colors):
            bb = relationship.bounding_box
            ax.add_patch(
                Rectangle(
                    (bb[0] * img_1_data.width, bb[1] * img_1_data.height),
                    bb[2] * img_1_data.width,
                    bb[3] * img_1_data.height,
                    fill=False,
                    edgecolor=color,
                    linewidth=3,
                )
            )
            sharpness_quotient = get_sharpness_quotient_of_bounding_box(img_1_data, bb)
            ax.text(
                bb[0] * img_1_data.width,
                bb[1] * img_1_data.height,
                relationship.Label1
                + f" ({relationship.Label2}) (Sharpness: {sharpness_quotient:.2f}",
                style="italic",
                bbox={"facecolor": "white", "alpha": 0.7, "pad": 10},
            )

    if regions_and_attributes_2:
        x_offset = img_1_data.width
        for relationship, color in zip(regions_and_attributes_2, colors):
            bb = relationship.bounding_box
            ax.add_patch(
                Rectangle(
                    (bb[0] * img_2_data.width + x_offset, bb[1] * img_2_data.height),
                    bb[2] * img_2_data.width,
                    bb[3] * img_2_data.height,
                    fill=False,
                    edgecolor=color,
                    linewidth=3,
                )
            )
            sharpness_quotient = get_sharpness_quotient_of_bounding_box(img_2_data, bb)
            ax.text(
                bb[0] * img_2_data.width + x_offset,
                bb[1] * img_2_data.height,
                relationship.Label1
                + f" ({relationship.Label2}) (Sharpness: {sharpness_quotient:.2f}",
                style="italic",
                bbox={"facecolor": "white", "alpha": 0.7, "pad": 10},
            )

    plt.tick_params(labelbottom="off", labelleft="off")
    plt.show()


def is_subj_attr_in_image(sample, subject, attribute):
    if sample.relationships:
        for relationship in sample.relationships.detections:
            if (
                relationship.Label1 in SYNONYMS[subject]
                and relationship.Label2 in SYNONYMS[attribute]
            ):
                return relationship

    return False


def high_bounding_box_overlap(bb1, bb2):
    """verify that bounding boxes are not duplicate annotations (actually the (almost) the same bounding box)"""
    diffs = [abs(b1 - b2) for b1, b2 in zip(bb1, bb2)]
    if np.all([diff < THRESHOLD_SAME_BOUNDING_BOX for diff in diffs]):
        return True
    return False


def find_other_subj_with_attr(sample, relationship_target, attribute):
    relationships = []
    if sample.relationships:
        for relationship in sample.relationships.detections:
            if relationship.Label1 in ["Boy", "Man"] and relationship_target.Label1 in [
                "Boy",
                "Man",
            ]:
                continue
            if relationship.Label1 in [
                "Girl",
                "Woman",
            ] and relationship_target.Label1 in ["Girl", "Woman"]:
                continue
            if (
                relationship.Label1 not in SYNONYMS[relationship_target.Label1]
                and relationship.Label2 in SYNONYMS[attribute]
            ):
                if not high_bounding_box_overlap(
                    relationship.bounding_box, relationship_target.bounding_box
                ):
                    if relationship_is_sharp(sample, relationship):
                        relationships.append(relationship)

    return relationships


def find_subj_with_other_attr(sample, subject, relationship_target):
    relationships = []
    if sample.relationships:
        for relationship in sample.relationships.detections:
            if (
                relationship.Label1 in SYNONYMS[subject]
                and relationship.Label2 not in SYNONYMS[relationship_target.Label2]
            ):
                if not high_bounding_box_overlap(
                    relationship.bounding_box, relationship_target.bounding_box
                ):
                    if relationship_is_sharp(sample, relationship):
                        relationships.append(relationship)

    return relationships


def get_duplicate_sample(sample, eval_set):
    for existing_sample in eval_set:
        if (
            existing_sample["img_example"] == sample["img_example"]
            and existing_sample["img_counterexample"] == sample["img_counterexample"]
        ) or (
            existing_sample["img_example"] == sample["img_counterexample"]
            and existing_sample["img_counterexample"] == sample["img_example"]
        ):
            if (
                existing_sample["relationship_target"].Label1
                == sample["relationship_target"].Label1
                and existing_sample["relationship_target"].Label2
                == sample["relationship_target"].Label2
            ):
                return existing_sample
    return None


def generate_eval_sets_from_noun_tuples(noun_tuples, max_samples):
    eval_sets = {}

    dataset = foz.load_zoo_dataset(
        "open-images-v6",
        label_types=["relationships"],
        max_samples=max_samples,
        dataset_name="open-images-v6",
    )

    for target_tuple in noun_tuples:
        print("Looking for: ", target_tuple)
        eval_set = []
        target_noun, distractor_noun = target_tuple

        # Compute matching images
        is_target = F("Label1").is_in(SYNONYMS[target_noun])
        is_distractor = F("Label1").is_in(SYNONYMS[distractor_noun])
        is_big_enough = (F("bounding_box")[2] > THRESHOLD_MIN_BOUNDING_BOX_WIDTH) & (
            F("bounding_box")[3] > THRESHOLD_MIN_BOUNDING_BOX_HEIGHT
        )
        matching_images = dataset.match(
            (
                F("relationships.detections").filter(is_target & is_big_enough).length()
                > 0
            )
            & (
                F("relationships.detections")
                .filter(is_distractor & is_big_enough)
                .length()
                > 0
            )
        )

        for example in tqdm(matching_images):
            possible_relationships = [
                rel
                for rel in example.relationships.detections
                if rel.Label1 in SYNONYMS[target_noun]
                and relationship_is_sharp(example, rel)
                and not is_subj_attr_in_image(
                    example, distractor_noun, rel.Label2
                )  # check that distractor IS NOT in same image
            ]
            possible_relationships = drop_synonyms(possible_relationships, "Label2")

            for relationship_target in possible_relationships:
                target_attribute = relationship_target.Label2

                # check that visual distractor IS in image
                rels_visual_distractor = find_subj_with_other_attr(
                    example, distractor_noun, relationship_target
                )

                for rel_visual_distractor in rels_visual_distractor:

                    # Start looking for counterexample image..
                    is_counterexample_relation = F("Label1").is_in(
                        SYNONYMS[distractor_noun]
                    ) & F("Label2").is_in(SYNONYMS[target_attribute])
                    matching_images_counterexample = matching_images.match(
                        F("relationships.detections")
                        .filter(is_counterexample_relation & is_big_enough)
                        .length()
                        > 0
                    )
                    # check that target IS NOT in same image:
                    matching_images_counterexample = [
                        im
                        for im in matching_images_counterexample
                        if not is_subj_attr_in_image(im, target_noun, target_attribute)
                    ]

                    for counterexample in matching_images_counterexample:
                        counterexample_possible_relationships = [
                            rel
                            for rel in counterexample.relationships.detections
                            if rel.Label1 in SYNONYMS[distractor_noun]
                            and rel.Label2 in SYNONYMS[target_attribute]
                            and relationship_is_sharp(counterexample, rel)
                        ]
                        counterexample_possible_relationships = drop_synonyms(
                            counterexample_possible_relationships, "Label2",
                        )

                        for (
                            counterex_relationship_target
                        ) in counterexample_possible_relationships:

                            # check that visual distractor IS in image
                            counterexample_rels_visual_distractor = find_subj_with_other_attr(
                                counterexample,
                                target_noun,
                                counterex_relationship_target,
                            )
                            for (
                                counterex_rel_visual_distractor
                            ) in counterexample_rels_visual_distractor:
                                sample = {
                                    "img_example": example.filepath,
                                    "img_counterexample": counterexample.filepath,
                                    "relationship_target": relationship_target,
                                    "relationship_visual_distractor": rel_visual_distractor,
                                    "counterexample_relationship_target": counterex_relationship_target,
                                    "counterexample_relationship_visual_distractor": counterex_rel_visual_distractor,
                                }
                                duplicate_sample = get_duplicate_sample(
                                    sample, eval_set
                                )

                                # Replace current sample if new one has bigger objects
                                if duplicate_sample is not None:
                                    if get_sum_of_bounding_box_sizes(
                                        sample
                                    ) > get_sum_of_bounding_box_sizes(duplicate_sample):
                                        eval_set.remove(duplicate_sample)
                                        eval_set.append(sample)

                                else:
                                    # show_image_pair(example.filepath, counterexample.filepath, [relationship_target, relationship_visual_distractor], [counterexample_relationship_target, counterexample_relationship_visual_distractor])

                                    # Add example and counter-example
                                    eval_set.append(sample)
        if len(eval_set) > 0:
            eval_sets[target_tuple] = eval_set
            print("saving intermediate results..")
            pickle.dump(eval_sets, open(f"results/noun-{max_samples}.p", "wb"))
            print(
                f"\nFound {len(eval_sets[target_tuple])} examples for {target_tuple}.\n"
            )

    return eval_sets


def generate_eval_sets_from_attribute_tuples(attribute_tuples, max_samples):
    dataset = foz.load_zoo_dataset(
        "open-images-v6",
        label_types=["relationships"],
        max_samples=max_samples,
        dataset_name="open-images-v6",
    )

    eval_sets = {}

    for target_tuple in attribute_tuples:
        print("Looking for: ", target_tuple)
        eval_set = []
        target_attribute, distractor_attribute = target_tuple

        # Compute matching images
        is_target = F("Label2").is_in(SYNONYMS[target_attribute])
        is_distractor = F("Label2").is_in(SYNONYMS[distractor_attribute])
        is_big_enough = (F("bounding_box")[2] > THRESHOLD_MIN_BOUNDING_BOX_WIDTH) & (
            F("bounding_box")[3] > THRESHOLD_MIN_BOUNDING_BOX_HEIGHT
        )
        matching_images = dataset.match(
            (
                F("relationships.detections").filter(is_target & is_big_enough).length()
                > 0
            )
            & (
                F("relationships.detections")
                .filter(is_distractor & is_big_enough)
                .length()
                > 0
            )
        )

        for example in tqdm(matching_images):
            relationships = [
                rel
                for rel in example.relationships.detections
                if rel.Label2 in SYNONYMS[target_attribute]
                and relationship_is_sharp(example, rel)
                and not is_subj_attr_in_image(
                    example, rel.Label1, distractor_attribute
                )  # check that distractor IS NOT in same image
            ]
            relationships = drop_synonyms(relationships, "Label1")

            for relationship_target in relationships:
                target_noun = relationship_target.Label1

                # check that visual distractor IS in image
                rels_visual_distractor = find_other_subj_with_attr(
                    example, relationship_target, distractor_attribute
                )

                for rel_visual_distractor in rels_visual_distractor:
                    # Start looking for counterexample image..
                    is_counterex_rel = F("Label1").is_in(SYNONYMS[target_noun]) & F(
                        "Label2"
                    ).is_in(SYNONYMS[distractor_attribute])
                    matching_images_counterexample = matching_images.match(
                        F("relationships.detections")
                        .filter(is_counterex_rel & is_big_enough)
                        .length()
                        > 0
                    )

                    # check that target IS NOT in same image:
                    matching_images_counterexample = [
                        im
                        for im in matching_images_counterexample
                        if not is_subj_attr_in_image(im, target_noun, target_attribute)
                    ]

                    for counterexample in matching_images_counterexample:

                        counterexample_relationships = [
                            rel
                            for rel in counterexample.relationships.detections
                            if rel.Label1 in SYNONYMS[target_noun]
                            and rel.Label2 in SYNONYMS[distractor_attribute]
                            and relationship_is_sharp(counterexample, rel)
                        ]
                        counterexample_relationships = drop_synonyms(
                            counterexample_relationships, "Label1",
                        )

                        for counterexample_rel_target in counterexample_relationships:
                            # check that visual distractor IS in image
                            counterex_rels_visual_distractor = find_other_subj_with_attr(
                                counterexample,
                                counterexample_rel_target,
                                target_attribute,
                            )

                            for (
                                counterex_rel_visual_distractor
                            ) in counterex_rels_visual_distractor:
                                sample = {
                                    "img_example": example.filepath,
                                    "img_counterexample": counterexample.filepath,
                                    "relationship_target": relationship_target,
                                    "relationship_visual_distractor": rel_visual_distractor,
                                    "counterexample_relationship_target": counterexample_rel_target,
                                    "counterexample_relationship_visual_distractor": counterex_rel_visual_distractor,
                                }
                                duplicate_sample = get_duplicate_sample(
                                    sample, eval_set
                                )

                                # Replace current sample if new one has bigger objects
                                if duplicate_sample is not None:
                                    if get_sum_of_bounding_box_sizes(
                                        sample
                                    ) > get_sum_of_bounding_box_sizes(duplicate_sample):
                                        eval_set.remove(duplicate_sample)
                                        eval_set.append(sample)
                                else:
                                    # show_image_pair(example.filepath, counterexample.filepath, [relationship_target, rel_visual_distractor], [counterexample_rel_target, counterex_rel_visual_distractor])

                                    # Add tuple of example and counter-example
                                    eval_set.append(sample)

        if len(eval_set) > 0:
            eval_sets[target_tuple] = eval_set
            print("saving intermediate results..")
            pickle.dump(eval_sets, open(f"results/attribute-{max_samples}.p", "wb"))
            print(
                f"Found {len(eval_sets[target_tuple])} examples for {target_tuple}.\n\n"
            )

    return eval_sets


def parse_args():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "--eval-set",
        type=str,
        required=True,
        choices=["noun_tuples", "attribute_tuples"],
    )
    argparser.add_argument(
        "--max-samples", type=int, default=None,
    )

    args = argparser.parse_args()

    return args


if __name__ == "__main__":
    args = parse_args()

    if args.eval_set == "noun_tuples":
        eval_sets_based_on_nouns = generate_eval_sets_from_noun_tuples(
            NOUN_TUPLES, args.max_samples
        )
        pickle.dump(
            eval_sets_based_on_nouns, open(f"results/noun-{args.max_samples}.p", "wb")
        )

    elif args.eval_set == "attribute_tuples":
        eval_sets = generate_eval_sets_from_attribute_tuples(
            ATTRIBUTE_TUPLES, args.max_samples
        )
        pickle.dump(eval_sets, open(f"results/attribute-{args.max_samples}.p", "wb"))
