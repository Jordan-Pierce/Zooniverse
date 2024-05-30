
import argparse
import sys
import glob

import pandas as pd
import statistics

from sklearn.cluster import OPTICS
import matplotlib.pyplot as plt
import matplotlib.patches as patches

import cv2
import os
import numpy as np
import supervision as sv


# ----------------------------------------------------------------------------------------------------------------------
# Functions
# ----------------------------------------------------------------------------------------------------------------------

def group_subjectid(df, num_samples, image_dir, output_dir, output_csv):

    #TODO: Group by subject id and then turn every new group into a separate dataframe

    # Group by subject ID
    df = pd.read_csv(df)
    df['Subject ID'] = df['Subject ID'].astype(int)
    df = df.groupby('Subject ID')

    count = 0
    detections = {}
    images = {}
    classes = ['ANTIPATHESFURCATA', 'ANTIPATHESATLANTICA', 'BEBRYCESP', 'MADRACISSP', 'MADREPORASP',
               'MURICEAPENDULA', 'PARAMURICIADESP', 'SWIFTIAEXSERTA', 'THESEANIVEA']

    # Runs through each subject ID group
    for subjectid, subjectid_df in df:
        print(subjectid)
        print("subject id", subjectid_df)

        # If there is only one annotation, skip clustering and reduction
        if len(subjectid_df) > 1:
            # Makes clusters and saves their labels
            labels = make_clusters(subjectid_df)

            # Reduce clusters and bounding boxes
            reduced_boxes = reduce_boxes(subjectid_df, labels)

            # Removes single clusters
            # NOTE: This is for testing purposes only
            no_single_clusters = remove_single_clusters(reduced_boxes)

            # Visually compare images with normal reductions to those with removed single clusters
            # NOTE: This is for testing purposes only
            image_path, image_name, jpg, media_id = get_image(reduced_boxes.iloc[0], image_dir)
            visual_compare(reduced_boxes, no_single_clusters, image_path, output_dir, image_name)

            # Drops the cluster column
            reduced_boxes = reduced_boxes.drop(columns=['clusters'])




            # # Experimenting with yolo conversion
            #
            # # Makes image folder if not already made
            # #os.makedirs(f"{output_dir}\\Yolo\\{media_id}", exist_ok=True)
            # detection = make_detection(reduced_boxes, classes)
            #
            # # Add detection to detections dict, this is our annotations argument
            # detections[jpg] = detection
            # #print("detections", detections)
            #
            # print("imagepath", image_path)
            # image = cv2.imread(image_path)
            # images[jpg] = image
            # print("testing", images)
            #
            # #ds2.as_folder_structure(output_dir)

        else:
            reduced_boxes = subjectid_df

            # Plot the single annotation
            image_path, image_name, jpg, media_id = get_image(reduced_boxes.iloc[0], image_dir)
            plot_boxes(reduced_boxes, image_path, image_name, output_dir)

        # Saves reduced annotations to csv
        #save_to_csv(output_csv, reduced_boxes)
        # print("images", images)
        #
        # ds = sv.DetectionDataset(classes=classes, images=images, annotations=detections)
        # # ds2 =sv.ClassificationDataset(classes=classes, images=images, annotations=detections)
        #
        # # print("ds", ds)
        #
        # # save as yolo format
        # yolo_images = f"{output_dir}\\images"
        # yolo_labels = f"{output_dir}\\labels"
        # print("check")
        #
        # ds.as_yolo(images_directory_path=yolo_images, annotations_directory_path=yolo_labels)
        # Checks if it is over the number of samples
        count += 1
        if count > num_samples:
            sys.exit(1)

    return filtered_df

def make_clusters(annotations):

    # Isolates x, y, width, and height values
    annotations = annotations[['x', 'y', 'w', 'h']]

    # Finds the center of each annotation bounding box
    centers = find_center(annotations)

    # Convert values into usable array for OPTICS clustering
    array = centers.to_numpy()
    #clust = OPTICS(min_samples=0.0, xi=0.01, min_cluster_size=None)
    clust = OPTICS(min_samples=0.0, cluster_method='dbscan', eps=100, min_cluster_size=None)
    clust.fit(array)

    # Saves the clustering labels
    labels = clust.labels_

    # Plots the clustering (OPTIONAL)
    #point_plot(array, labels)

    return labels

def find_center(df):

    x_centers = []
    y_centers = []

    # Find the center of a rectangle for each annotation
    for i, row in df.iterrows():
        x_center = row['x'] + row['w'] / 2
        y_center = row['y'] + row['h'] / 2

        x_centers.append(x_center)
        y_centers.append(y_center)

    # Creates centers dataframe
    centers = pd.DataFrame({'x_center': x_centers, 'y_center': y_centers})

    return centers

def point_plot(array, labels):
    # plot the clustering graph
    plt.figure(figsize=(8, 6))
    scatter = plt.scatter(array[:, 0], array[:, 1], c=labels, s=50, alpha=0.6, cmap='viridis')
    print("check")
    legend1 = plt.legend(*scatter.legend_elements(), title="Clusters")
    plt.gca().add_artist(legend1)
    plt.title('OPTICS Clustering')
    plt.xlabel('Feature 1')
    plt.ylabel('Feature 2')
    plt.grid(True)
    plt.show()

def reduce_boxes(values, labels):

    # Add clusters as a column to the dataframe
    values = values.assign(clusters=labels)

    # Group by cluster
    clusters = values.groupby('clusters')

    columns = ['x', 'y', 'w', 'h', 'label']
    reduced = pd.DataFrame(columns=columns)

    # Iterate through the cluster groups
    for cluster, cluster_df in clusters:

        # Ignore if it has a cluster size of 1
        if cluster == -1:
            # Add directly to reduced annotations
            reduced = pd.concat([reduced, cluster_df], ignore_index=True)
            continue
        else:
            # Find the bounding box of best fit for the cluster
            avg_bbox = np.mean(cluster_df[['x', 'y', 'w', 'h']], axis=0)
            avg_bbox = pd.DataFrame(avg_bbox).T

            # Get the mode label for the box
            mode = statistics.mode(cluster_df['label'])
            avg_bbox['label'] = mode

            #TODO: This could definitely be done better

            # Add in the missing columns
            new_row = cluster_df.iloc[0]
            new_row = pd.DataFrame(new_row).T
            new_row = new_row.drop(columns=['x', 'y', 'w', 'h', 'label'])
            new_row.reset_index(drop=True, inplace=True)
            avg_bbox.reset_index(drop=True, inplace=True)
            new_row = pd.concat([new_row, avg_bbox], axis=1)

            # Add best-fit bounding box to reduced dataframe
            reduced = pd.concat([reduced, new_row], ignore_index=True)

    # Plot the reduced clustering (OPTIONAL)
    #point_plot(reduced.to_numpy(), reduced.index)

    return(reduced)

def remove_single_clusters(df):

    no_single_clusters = pd.DataFrame()

    # Iterates through rows of annotations to find cluster id of -1
    for i, row in df.iterrows():
        if row['clusters'] != -1:
            no_single_clusters = no_single_clusters._append(row, ignore_index=True)

    return no_single_clusters

def remove_big_boxers(final_bbox):

    # iterates through the rows of annotations to find cluster id of -1
    for i, row in final_bbox.iterrows():
        if row['clusters'] == -1:
            # the bbox may be a big boxer
            #print("row", row)
            percent = total_overlap(row, final_bbox)
            print("percent", percent)

            # remove boxes that have significant overlap
            if percent > 0.25:
                final_bbox.drop(final_bbox.index[i], inplace=True)
        else:
            continue
    print("final", final_bbox)

    return final_bbox

def total_overlap(box, all_boxes):

    total_overlap_area = 0
    num_overlaps = 0
    total_other_box_area = 0

    for i, other_box in all_boxes.iterrows():
        # test to see if it's the same as box
        # print("other", other_box)
        # print("box", box)
        if other_box.equals(box):
            print("samesies")
            continue
        else:

            # Calculate the coordinates of the intersection rectangle
            x1 = max(box['x'], other_box['x'])
            y1 = max(box['y'], other_box['y'])
            x2 = min(box['x'] + box['w'], other_box['x'] + other_box['w'])
            y2 = min(box['y'] + box['h'], other_box['y'] + other_box['h'])

            # If the intersection is valid (non-negative area), calculate the area
            if x1 < x2 and y1 < y2:
                overlap_area = (x2 - x1) * (y2 - y1)
                num_overlaps += 1
                total_overlap_area += overlap_area

                # total area of the other boxes that are overlapping
                other_box_area = other_box['w'] * other_box['h']
                total_other_box_area += other_box_area

    print("overlap area", total_overlap_area)
    print("number of overlaps", num_overlaps)

    if num_overlaps == 0:
        return 0
    else:
        # calculate percentage
        percent = total_overlap_area / total_other_box_area

        return percent

def get_image(row, image_dir):

    # Get the meta
    media_id = int(row['Media ID'])
    frame_name = row['Frame Name']

    # Give name to the image
    image_name = f"{media_id} - {frame_name}"
    jpg_name = f"{media_id}.jpg"

    # Get media folder, the frame path
    media_folders = glob.glob(f"{image_dir}\\*")
    media_folder = [f for f in media_folders if str(media_id) in f][0]
    frame_path = f"{media_folder}\\frames\\{frame_name}"

    return frame_path, image_name, jpg_name, media_id

def plot_boxes(df, image_path, image_name, output_dir):

    image = plt.imread(image_path)

    for i, r in df.iterrows():
        # Extract the values of this annotation
        x, y, w, h = r[['x', 'y', 'w', 'h']]

        # Create the figure
        rect = patches.Rectangle((x, y), w, h, linewidth=2, edgecolor='black', facecolor='none')
        plt.gca().add_patch(rect)

        # Plot the class label on the bbox
        plt.text(x + w * 0.02,
                y + h * 0.98,
                r['label'],
                color='white', fontsize=8,
                ha='left', va='top',
                bbox=dict(facecolor='black', alpha=0.5))

    # Save with same name as frame in examples folder
    plt.title(f"{image_name}")
    plt.imshow(image)
    plt.savefig(f"{output_dir}\\Visual_Comparison\\{image_name}", bbox_inches='tight')
    # plt.close()


def save_to_csv(output_csv, annotations):

    # Get rid of unnecessary information
    annotations = annotations.drop(columns=['classification_id', 'user_name', 'user_ip', 'created_at', 'retired', 'user_id', 'Unnamed: 0'])

    # Save the annotations to a csv file
    if os.path.isfile(output_csv):
        annotations.to_csv(output_csv, mode='a', header=False, index=False)
    else:
        annotations.to_csv(output_csv, index=False)

def visual_compare(annotations1, annotations2, image_path, output_dir, image_name):

    image = plt.imread(image_path)

    # Plot the images side by side
    plt.figure(figsize=(10, 5))

    # Plot image 1 on the left subplot
    plt.subplot(1, 2, 1)
    plt.imshow(image)
    for i, r in annotations1.iterrows():
        # Extract the values of this annotation
        x, y, w, h = r[['x', 'y', 'w', 'h']]
        # Create the figure
        rect = patches.Rectangle((x, y), w, h, linewidth=2, edgecolor='black', facecolor='none')
        plt.gca().add_patch(rect)

        # Plot the class label on the bbox
        plt.text(x + w * 0.02,
                y + h * 0.98,
                r['label'],
                color='white', fontsize=8,
                ha='left', va='top',
                bbox=dict(facecolor='black', alpha=0.5))
    plt.title('With Single Clusters')

    # Plot image 2 on the right subplot
    plt.subplot(1, 2, 2)
    plt.imshow(image)
    for i, r in annotations2.iterrows():
        # Extract the values of this annotation
        x, y, w, h = r[['x', 'y', 'w', 'h']]
        # Create the figure
        rect = patches.Rectangle((x, y), w, h, linewidth=2, edgecolor='black', facecolor='none')
        plt.gca().add_patch(rect)

        # Plot the class label on the bbox
        plt.text(x + w * 0.02,
                y + h * 0.98,
                r['label'],
                color='white', fontsize=8,
                ha='left', va='top',
                bbox=dict(facecolor='black', alpha=0.5))
    plt.title('Without Single Clusters')

    plt.savefig(f"{output_dir}\\Visual_Comparison\\{image_name}", bbox_inches='tight')

def make_detection(annotations, class_labels):

    # Create arrays for bounding boxes and classes
    xyxy = np.empty((len(annotations), 4))
    classes = np.empty(len(annotations), dtype=object)
    # print(annotations)
    # print(class_labels)

    for i, row in annotations.iterrows():
        x1 = row['x']
        y1 = row['y']
        x2 = x1 + row['w']
        y2 = y1 + row['h']

        xyxy[i] = [x1, y1, x2, y2]

        j = -1
        for cl in class_labels:
            j += 1
            if cl == row['label']:
                classes[i] = j

    print(classes)

    # Create a Detection dataclass for an image
    detection = sv.Detections(xyxy=xyxy, class_id=classes)
    print(detection)

    return detection


def main():
    parser = argparse.ArgumentParser(description="Reduce annotations for an image frame")

    parser.add_argument("-csv", type=str,
                        help="Input CSV file")

    # parser.add_argument("-id", type=int,
    #                     #default=98330167, #
    #                     #default=98330569, #26313.jpg
    #                     #default=98330111, #21368.jpg
    #                     #default=98330065, #8661.jpg
    #                     #default=98330040, #269.jpg
    #                     #default=98330575,
    #                     #default=98361988, #199870.jpg
    #                     #default=98333601, #175594.jpg
    #                     help="Subject ID")

    parser.add_argument("-image_dir", #type=str,
                        help="The image directory")

    parser.add_argument("-output_dir", #type=str,
                         help="Output directory")

    parser.add_argument("-num_samples", type=int,
                        default=1,
                        help="Number of samples to run through")

    parser.add_argument("--season_num", type=int,
                        default=1,
                        help="Season number.")


    args = parser.parse_args()

    # parse out arguments
    season_num = args.season_num
    input_csv = args.csv
    num_samples = args.num_samples

    image_dir = f"{args.image_dir}\\Season_{season_num}"
    output_dir = f"{args.output_dir}\\Reduced"

    # Create output csv file
    output_csv = f"{output_dir}\\reduced_annotations.csv"

    # Make the output directory
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(f"{output_dir}\\Visual_Comparison", exist_ok=True)
    os.makedirs(f"{output_dir}\\Yolo", exist_ok=True)



    try:
        annotations = group_subjectid(input_csv, num_samples, image_dir, output_dir, output_csv)

        # labels = make_clusters(annotations)
        #
        # final_bbox = reduce_boxes(annotations, labels)
        #
        # no_single_clusters = remove_single_clusters(final_bbox)
        #
        # visual_compare(final_bbox, no_single_clusters, args.image)

        #save_to_csv(output_csv, final_bbox)

        #plot_boxes(final_bbox, args.image)

        #removed = remove_big_boxers(final_bbox)

        #plot_boxes(removed, args.image, args.label_dir)

        print("Done.")

    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    main()