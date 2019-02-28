import cv2
import math
import numpy as np

from scipy.interpolate import griddata

def apply_mask(np_array, mask):
    return cv2.bitwise_and(np_array, np_array, mask=mask)

def get_binary_mask(np_array, cv2_mask):
    if cv2_mask is None:
        return None, None, None

    # Get areas where there are holes in the data
    nimg = cv2.normalize(src=np_array, dst=None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
    quality, holeMask = cv2.threshold(nimg, 10, 255, cv2.THRESH_BINARY_INV)

    # The two reds in MS Paint are
    # Bright Red: 236, 28, 36
    # Dark Red: 136, 0, 27
    # Try to support both here
    red_pixels = np.logical_and(np.logical_and(cv2_mask[:,:,0] < 40, cv2_mask[:,:,1] < 40), cv2_mask[:,:,2] > 130)
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

# Uses scipy griddata to interpolate and "recompute" the terrain data based on only the valid image points
# Seems to produce a smoother and more natural result
# Also allows us to sample in arbitrary sizes
def infill_image_scipy(np_array, cv2_mask, background_ratio=16.0, printf=print):
    holeMask, remove_mask, keep_mask = get_binary_mask(np_array, cv2_mask)

    # Get valid pixel elevations
    full_points_list = []
    full_values_list = []

    points_list = []
    values_list = []

    output_list = []

    printf("Finding valid masked points")
    for row in np.arange(0, np_array.shape[0]):
        for column in np.arange(0, np_array.shape[1]):
            value = np_array[row, column][0]
            masked = 0 # Pass through by default
            if holeMask is not None:
                masked = holeMask[row, column]

            # Need to output a high resolution pixel for every pixel in original
            output_list.append([row, column])

            # Don't interpolate on invalid points
            if not math.isnan(value):
                # Background requires every valid point
                full_points_list.append([row, column])
                full_values_list.append(value)
                if masked < 1:
                    # Only feed masked points into high resolution
                    points_list.append([row, column])
                    values_list.append(value)

    points = np.array(points_list)
    values = np.array(values_list)
    outs = np.array(output_list)

    background_map = None
    if background_ratio is not None:
        printf("Generating low detail background")
        starts = np.amin(output_list, axis=0)
        ends = np.amax(output_list, axis=0)
        background_row_count = math.ceil((ends[0]-starts[0])/background_ratio)
        background_col_count = math.ceil((ends[1]-starts[1])/background_ratio)
        background_outs = np.mgrid[starts[0]:ends[0]:background_ratio, starts[1]:ends[1]:background_ratio].reshape(2,-1).T
        background_grid_z = griddata(full_points_list, full_values_list, background_outs, method='linear', fill_value=-1.0)
        background_map = background_grid_z.reshape((background_row_count, background_col_count))

    printf("Removing holes")
    detail_grid_z = griddata(points, values, outs, method='linear', fill_value=-1.0)  

    if remove_mask is not None:
        return apply_mask(detail_grid_z.reshape(np_array.shape), remove_mask), background_map, holeMask
    else:
        return detail_grid_z.reshape(np_array.shape), background_map, holeMask
