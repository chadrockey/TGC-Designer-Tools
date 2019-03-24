import cv2
import math
import numpy as np

from scipy.interpolate import griddata

def apply_mask(np_array, mask, invalid_value=math.nan):
    np_array[ mask < 1 ] = invalid_value
    return np_array

def get_binary_mask(cv2_mask):
    if cv2_mask is None:
        return None, None

    # The two reds in MS Paint are
    # Bright Red: 236, 28, 36
    # Dark Red: 136, 0, 27
    # Try to support both here
    red_pixels = np.logical_and(np.logical_and(cv2_mask[:,:,0] < 40, cv2_mask[:,:,1] < 40), cv2_mask[:,:,2] > 130)

    # The blues in Paint3d are:
    # Indigo: 62, 73, 204
    # Turquoise: 0, 168, 243
    blue_pixels = np.logical_and(np.logical_and(cv2_mask[:,:,0] > 200, cv2_mask[:,:,1] < 180), cv2_mask[:,:,2] < 70)

    # Don't infill areas painted in Red
    # Red turns to black, otherwise, white.  Black will not be infilled or sent in the output image
    remove_mask = (255.0*np.ones((cv2_mask.shape[0], cv2_mask.shape[1], 1))).astype('uint8')
    remove_mask[red_pixels] = 0

    # Preserve original terrain for areas marked in Blue
    preserve_mask = (np.zeros((cv2_mask.shape[0], cv2_mask.shape[1], 1))).astype('uint8')
    preserve_mask[blue_pixels] = 255

    return remove_mask, preserve_mask

# Uses scipy griddata to interpolate and "recompute" the terrain data based on only the valid image points
# Seems to produce a smoother and more natural result
# Also allows us to sample in arbitrary sizes
def infill_image_scipy(np_array, cv2_mask, background_ratio=16.0, fill_water=False, purge_water=False, printf=print):
    remove_mask, preserve_mask = get_binary_mask(cv2_mask)

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
            masked = 1 # Pass through by default
            if remove_mask is not None:
                masked = remove_mask[row, column]

            # Need to output a high resolution pixel for every pixel in original
            output_list.append([row, column])

            # Don't interpolate on invalid points
            if not math.isnan(value):
                # Background requires every valid point
                full_points_list.append([row, column])
                full_values_list.append(value)
                if masked  > 0:
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

    printf("Filling missing data in heightmap")
    detail_grid_z = griddata(points, values, outs, method='linear', fill_value=math.nan)

    if remove_mask is not None:
        # Make sure that pixels marked red are not used
        red_masked = apply_mask(detail_grid_z.reshape(np_array.shape), remove_mask)
        blue_indices = preserve_mask > 0
        # If a pixel is blue, use the original pre-infilled values
        # This helps populate water features, etc
        if not fill_water:
            red_masked[blue_indices] = np_array[blue_indices]
        if purge_water:
            # Remove all terrain that is masked as blue
            red_masked[blue_indices] = math.nan
        return red_masked, background_map, remove_mask
    else:
        return detail_grid_z.reshape(np_array.shape), background_map, remove_mask
