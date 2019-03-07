import cv2
import imutils
import math
import numpy as np
from scipy import ndimage
from scipy.ndimage import label
from skimage.feature import peak_local_max
from skimage.morphology import watershed
from skimage.color import label2rgb

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import cm

import infill_image

def getTreeHeight(normalized_heightmap, x, y):
    center_x = round(x)
    center_y = round(y)

    # Check this many pixels around center
    area_width = 1

    # Make sure we're on the map
    if center_x < area_width or center_y < area_width:
        return None
    if center_x > normalized_heightmap.shape[1] - area_width or center_y > normalized_heightmap.shape[0] - area_width:
        return None

    return np.max(normalized_heightmap[center_y-area_width:center_y+area_width, center_x-area_width:center_x+area_width])

def getTreeCoordinates(groundmap, objectmap, printf=print):
    printf("Finding height offsets from groundmap to objects")

    # Tuning constants
    estimated_tree_size = 5 # Blurring constant for guassian blur.  Without this, larger trees may split apart into smaller ones
    minimum_tree_height = 3.5
    minimum_tree_distance = int(4) # Minimum distance between trees, prevents small overlapping partial trees

    #groundmap, background_image, holeMask = infill_image.infill_image_scipy(groundmap, None, background_ratio=None, printf=printf)
    #objectmap, background_image, holeMask = infill_image.infill_image_scipy(objectmap, None, background_ratio=None, printf=printf)

    #fig, ax = plt.subplots()
    #im = ax.imshow(groundmap[:,:,0], origin='lower', cmap=cm.plasma)

    #fig2, ax2 = plt.subplots()
    #im2 = ax2.imshow(objectmap[:,:,0], origin='lower', cmap=cm.plasma)

    normalized_heightmap = np.subtract(objectmap, groundmap)
    # Set very large values to Invalid.  Sometimes there are random points high up in the air and these messs up the tree detection
    outliers = np.isfinite(normalized_heightmap) # Prints a warning if you try to compare to a NaN, so filter those out
    outliers[outliers] &= normalized_heightmap[outliers] > 40.0
    normalized_heightmap[outliers] = math.nan
    # Todo is hole filling needed?
    normalized_heightmap, background_image, holeMask = infill_image.infill_image_scipy(normalized_heightmap, None, background_ratio=None, printf=printf)

    fig3, ax3 = plt.subplots()
    im3 = ax3.imshow(normalized_heightmap[:,:,0], origin='lower', cmap=cm.plasma)

    smoothed = cv2.GaussianBlur(np.copy(normalized_heightmap), (estimated_tree_size, estimated_tree_size), 0) 

    #fig4, ax4 = plt.subplots()
    #im4 = ax4.imshow(smoothed, origin='lower', cmap=cm.plasma)

    # Pre-processing.
    '''img_float = (np.copy(smoothed) - np.min(smoothed)) / (np.max(smoothed) - np.min(smoothed)) # Normalize to 1.0
    img_gray = (255.0*img_float).astype(np.uint8)
    _, img_bin = cv2.threshold(np.copy(img_gray), 0, 255, cv2.THRESH_OTSU)
    img_bin = cv2.morphologyEx(img_bin, cv2.MORPH_OPEN, np.ones((1, 1), dtype=int))

    fig6, ax6 = plt.subplots()
    im6 = ax6.imshow(img_bin, origin='lower', cmap=cm.plasma)

    D = ndimage.distance_transform_edt(img_bin)
    localMax = peak_local_max(D, indices=False, min_distance=minimum_tree_distance, labels=img_bin, exclude_border=True)
    markers = ndimage.label(localMax, structure=np.ones((3, 3)))[0] # structure is 8 connected direction matrix
    labels = watershed(-D, markers, mask=img_bin)
    printf("{} unique trees found".format(len(np.unique(labels)) - 1))'''

    min_height = np.min(smoothed)
    max_height = np.max(smoothed)
    img_float = (np.copy(smoothed) - min_height) / (max_height - min_height) # Normalize to 1.0
    img_gray = (255.0*img_float).astype(np.uint8)
    uint8_thresh = 255.0*(minimum_tree_height - min_height)/(max_height - min_height)
    print("INT THRESHOLD IS: " + str(uint8_thresh))
    _, img_bin = cv2.threshold(np.copy(img_gray), uint8_thresh, 255, cv2.THRESH_OTSU)
    img_morph = cv2.morphologyEx(img_bin, cv2.MORPH_OPEN, np.ones((1, 1), dtype=int))
    D = ndimage.distance_transform_edt(img_morph)

    fig6, ax6 = plt.subplots()
    im6 = ax6.imshow(img_bin, origin='lower', cmap=cm.plasma)

    fig67, ax67 = plt.subplots()
    im67 = ax67.imshow(-D, origin='lower', cmap=cm.plasma)

    canopy_only =  cv2.bitwise_and(smoothed, smoothed, mask=img_bin)

    # Identify each tree peak in the canopy only image
    #localMax = peak_local_max(canopy_only, indices=False, min_distance=minimum_tree_distance, threshold_abs=minimum_tree_height, exclude_border=True)
    localMax = peak_local_max(D, indices=False, min_distance=minimum_tree_distance, labels=img_morph, exclude_border=True)
    markers = ndimage.label(localMax, structure=np.ones((3, 3)))[0] # structure is 8 connected direction matrix
    labels = watershed(-D, markers, mask=img_bin, connectivity=2)
    printf("{} unique trees found".format(len(np.unique(labels)) - 1))


    image = np.copy(img_gray)
    image  = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    fig66, ax66 = plt.subplots()
    im66 = ax66.imshow(label2rgb(labels, image=image, bg_label=0), origin='lower')

    # image_max is the dilation of im with a 20*20 structuring element
    # It is used within peak_local_max function
    '''image_max = ndimage.maximum_filter(canopy_only, size=minimum_tree_distance*2, mode='constant')

    # Comparison between image_max and im to find the coordinates of local maxima
    coordinates = peak_local_max(canopy_only, min_distance=minimum_tree_distance, threshold_abs=minimum_tree_height)

    # display results
    fig88, ax88 = plt.subplots()
    fig, axes = plt.subplots(1, 3, figsize=(8, 3), sharex=True, sharey=True)
    ax = axes.ravel()
    ax[0].imshow(img_float, origin='lower', cmap=plt.cm.gray)
    ax[0].axis('off')
    ax[0].set_title('Original')

    ax[1].imshow(image_max, origin='lower', cmap=plt.cm.gray)
    ax[1].axis('off')
    ax[1].set_title('Maximum filter')

    ax[2].imshow(img_float, origin='lower', cmap=plt.cm.gray)
    ax[2].autoscale(False)
    ax[2].plot(coordinates[:, 1], coordinates[:, 0], 'r.')
    ax[2].axis('off')
    ax[2].set_title('Peak local max')

    fig.tight_layout()'''


    #fig0, ax0 = plt.subplots()
    #im0 = ax0.imshow(img_bin, origin='lower', cmap=cm.plasma)

    # loop over the unique labels returned by the Watershed
    # algorithm
    image[:,:,0] = 255*localMax # Draw maxima in red
    # Green is reserved for trees
    image[:,:,2] = 0*localMax # Clear Blue
    output_trees = []
    # TODO Add status print here
    for label in np.unique(labels):
        # if the label is zero, we are examining the 'background'
        # so simply ignore it
        if label == 0:
            continue
     
        # otherwise, allocate memory for the label region and draw
        # it on the mask
        mask = np.zeros(img_gray.shape, dtype="uint8")
        mask[labels == label] = 255
     
        # detect contours in the mask and grab the largest one
        cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        c = max(cnts, key=cv2.contourArea)
     
        # Get the position and radius of the tree
        ((x, y), r) = cv2.minEnclosingCircle(c)
        # Now get the height of the tree
        height = getTreeHeight(normalized_heightmap, x, y)
        if height:
            cv2.circle(image, (int(x), int(y)), int(r), (0, 0, 255), 1, lineType=cv2.LINE_AA)
            #printf((x, y, r, height))
            # Return trees in x, y, radius, height
            output_trees.append((x, y, r, height))

    fig7, ax7 = plt.subplots()
    im7 = ax7.imshow(image, origin='lower')

    plt.show()

    return output_trees
