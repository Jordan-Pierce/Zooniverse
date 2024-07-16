import os
import random
import argparse

import traceback
import numpy as np
import pandas as pd
from datetime import datetime as dt

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from sklearn.metrics import auc
from reduce_annotations import get_image, remove_single_clusters
from visualize import create_image_row
from reduce_annotations import save_to_csv, get_now

# ----------------------------------------------------------------------------------------------------------------------
# Functions
# ----------------------------------------------------------------------------------------------------------------------


def annotation_count(retirement_dir, output_dir, image_dir, threshold):

    # Initialize dataframe
    counts = pd.DataFrame(columns=['Retirement_Age', 'Reduced_Annotation_Number', 'Extracted_Annotation_Number'])

    for dir in os.listdir(retirement_dir):

        age = int(dir.split("_", 1)[1])

        #dir = f"{retirement_dir}/{dir}/Reduced"
        dir = f"{retirement_dir}/{dir}"

        reduced = [file for file in os.listdir(dir) if file.startswith("reduced")][0]

        extracted = [file for file in os.listdir(dir) if file.startswith("extracted")][0]

        reduced = pd.read_csv(f"{dir}/{reduced}")
        extracted = pd.read_csv(f"{dir}/{extracted}")

        image_df = group_annotations(reduced, extracted, dir, image_dir, threshold)

        print(image_df)

        # Create output CSV file for reduced annotations
        output_csv = f"{dir}/image_info"

        # Get the timestamp
        timestamp = get_now()

        save_to_csv(output_csv, image_df, False, timestamp)

        reduced_number = len(reduced)
        extracted_number = len(extracted)

        # Add to dataframe
        new_row = {'Retirement_Age': age, 'Reduced_Annotation_Number': reduced_number,
                   'Extracted_Annotation_Number': extracted_number}

        counts = counts._append(new_row, ignore_index=True)

    print(counts)

    counts.sort_values(by='Retirement_Age')

    # Initialize the plot
    fig, axs = plt.subplots(ncols=2, figsize=(20, 10))

    # Plot the left subplot for reduced annotations
    axs[0].bar(counts['Retirement_Age'], counts['Reduced_Annotation_Number'], width=3)
    #axs[0].set_ylim(0.0, 1.0)
    #axs[0].set_xlim(xmin=0.0)
    axs[0].set_title("Reduced Annotations")

    # Plot right subplot for original annotations
    axs[1].bar(counts['Retirement_Age'], counts['Extracted_Annotation_Number'], width=3)
    #axs[1].set_xlim(xmin=0.0)
    axs[1].set_title("Original Annotations")

    # Set axis labels
    fig.supylabel("Number of Annotations")
    fig.supxlabel("Retirement Age")

    plt.tight_layout()

    # Save the plot
    plt.show()
    plt.savefig(f"{output_dir}/annotation_count_comparison.jpg", bbox_inches='tight')
    plt.close()


def group_annotations(reduced_annotations, extracted_annotations, output_dir, image_dir, threshold):

    # Make the subject ID's integers
    extracted_annotations['Subject ID'] = extracted_annotations['Subject ID'].astype(int)
    reduced_annotations['Subject ID'] = reduced_annotations['Subject ID'].astype(int)

    # Group both dataframes by subject ID
    extracted_groups = extracted_annotations.groupby("Subject ID")
    reduced_groups = reduced_annotations.groupby("Subject ID")

    # Initialize metrics dataframe
    metrics_df = pd.DataFrame(columns=['Subject ID', 'Average_IoU', 'Precision',
                                       'Recall', 'image_path', 'Number_of_Annotations', 'Mean_Average_Precision'])

    # Loop through the subject IDs in the original annotations
    for subject_id, subject_id_df in extracted_groups:

        print("Subject ID", subject_id)
        print("Subject Annotations", subject_id_df)

        # Get image information
        image_path, image_name, frame_name = get_image(subject_id_df.iloc[0], image_dir)

        # Get the reduced annotations for the subject ID
        if (reduced_annotations['Subject ID'] == subject_id).any():
            reduced_subject_id = reduced_groups.get_group(subject_id)

            # Get new dataframe
            no_singles = remove_single_clusters(subject_id_df)

            metrics_df = create_image_row(no_singles, subject_id, metrics_df, image_path, image_name, threshold)
        else:
            continue

    return metrics_df


def

# -----------------------------------------------------------------------------
# Main Function
# -----------------------------------------------------------------------------

def main():
    """

    """

    parser = argparse.ArgumentParser(description="Determine the minimum retirement age for images in Zooniverse")

    parser.add_argument("--retirement_dir", type=str,
                        default="./Retirement",
                        help="The directory comparing retirement ages to compare")

    parser.add_argument("--output_dir", type=str,
                        default="./Retirement",
                        help="Output directory")

    parser.add_argument("--image_dir", type=str,
                        default="./Data",
                        help="Image directory")

    parser.add_argument("--iou_threshold", type=float,
                        default=0.6,
                        help="The IoU threshold to be used for mAP")

    args = parser.parse_args()

    # Parse out arguments
    retirement_dir = args.retirement_dir
    #output_dir = args.output_dir
    image_dir = args.image_dir
    output_dir = retirement_dir
    iou_threshold = args.iou_threshold

    try:

        annotation_count(retirement_dir, output_dir, image_dir, iou_threshold)

        print("Done.")

    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()