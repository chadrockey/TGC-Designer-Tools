import cv2

import numpy as np
import cv2

from scipy.interpolate import griddata

def apply_mask(np_array, mask):
    return cv2.bitwise_and(np_array, np_array, mask=mask)

def get_binary_mask(np_array, cv2_mask):
    # Get areas where there are holes in the data
    nimg = cv2.normalize(src=np_array, dst=None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
    quality, holeMask = cv2.threshold(nimg, 10, 255, cv2.THRESH_BINARY_INV)

    red_pixels = np.logical_and(np.logical_and(cv2_mask[:,:,0] < 20, cv2_mask[:,:,1] < 20), cv2_mask[:,:,2] > 230)
    blue_pixels = np.logical_and(np.logical_and(cv2_mask[:,:,0] > 230, cv2_mask[:,:,1] < 20), cv2_mask[:,:,2] < 20)

    # Don't infill areas painted in 255 Red in cv2_mask
    # Red turns to black, otherwise, white.  Black will not be infilled or sent in the output image
    remove_mask = (255.0*np.ones((cv2_mask.shape[0], cv2_mask.shape[1], 1))).astype('uint8')
    remove_mask[red_pixels] = 0

    # Keep areas that are 255 Blue in cv2_mask
    # Blue turns to black, otherwise white.  Black will not be infilled, input preserved values in output image
    keep_mask = (255.0*np.ones((cv2_mask.shape[0], cv2_mask.shape[1], 1))).astype('uint8')
    keep_mask[blue_pixels] = 0.0

    # Mask the holeMask with with red and blue masks
    holeMask = apply_mask(holeMask, remove_mask)
    #holeMask = apply_mask(holeMask, keep_mask) # Don't preserve lakes since we're drawing them as spines in cartpath

    return holeMask, remove_mask, keep_mask

# Image as numpy array
def infill_image(np_array, cv2_mask):
    holeMask, remove_mask, keep_mask = get_binary_mask(np_array, cv2_mask)

    dst = cv2.inpaint(np_array,holeMask,3,cv2.INPAINT_NS)

    # Remove the remove mask from the original parts of the image
    dst = apply_mask(dst, remove_mask)
    # Also remove the water mask, even thought it was used to fill in data
    #dst = apply_mask(dst, keep_mask)

    return (dst, holeMask)

# Uses scipy griddata to interpolate and "recompute" the terrain data based on only the valid image points
# Seems to produce a smoother and more natural result
# Also allows us to sample in arbitrary sizes
def infill_image_scipy(np_array, cv2_mask):
    holeMask, remove_mask, keep_mask = get_binary_mask(np_array, cv2_mask)

    # Get valid pixel elevations
    points_list = []
    values_list = []

    output_list = []

    for row in np.arange(0, np_array.shape[0]):
        for column in np.arange(0, np_array.shape[1]):
            masked = holeMask[row, column]

            output_list.append([row, column])

            if masked < 1:
                # Valid point, feed into algorithm
                points_list.append([row, column])
                values_list.append(np_array[row, column][0])

    points = np.array(points_list)
    values = np.array(values_list)
    outs = np.array(output_list)

    grid_z = griddata(points, values, outs, method='linear', fill_value=-1.0)

    return apply_mask(grid_z.reshape(np_array.shape), remove_mask), holeMask
