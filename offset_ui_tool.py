import cv2
import json
import math
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.widgets import RectangleSelector
from matplotlib.widgets import RadioButtons, Slider, Button
import numpy as np
import sys
import time
import urllib

import OSMTGC
import tgc_tools
from usgs_lidar_parser import *

import cv2
import json
import math
import numpy as np
from pathlib import Path
import sys

from GeoPointCloud import GeoPointCloud
from infill_image import infill_image_scipy
import OSMTGC
import tgc_tools

from functools import partial

def drawNewImage(ax, image_dict, label):
    ax.imshow(image_dict[label], origin='lower')
    plt.draw()

def drawNewLocation(ax, image_dict, result, image_scale, radio, sx, sy, event, ar):
    x_offset = 0.0
    y_offset = 0.0
    if sx is not None and sy is not None:
        x_offset = sx.val
        y_offset = sy.val

    vosm = np.copy(image_dict["Visible"])
    vosm = OSMTGC.addOSMToImage(result.ways, vosm, pc, image_scale, x_offset, y_offset)
    image_dict["Visible Golf"] = vosm

    hosm = np.copy(image_dict["Heightmap"]).astype('float32')
    hosm = np.clip(hosm, 0.0, 3.5*np.median( hosm[ hosm >= 0.0 ])) # Limit outlier pixels
    hosm = hosm / np.max(hosm)
    hosm = cv2.cvtColor(hosm, cv2.COLOR_GRAY2RGB)
    hosm = OSMTGC.addOSMToImage(result.ways, hosm, pc, image_scale, x_offset, y_offset)
    image_dict["Heightmap Golf"] = hosm

    # Always set to Visible Golf after drawing new golf features
    ax.imshow(image_dict["Visible Golf"], origin='lower')
    radio.set_active(1)

def getManualRegistrationError(visual, heightmap, image_scale, pc):
    upper_left_enu = pc.ulENU()
    lower_right_enu = pc.lrENU()
    upper_left_latlon = pc.enuToLatLon(*upper_left_enu)
    lower_right_latlon = pc.enuToLatLon(*lower_right_enu)
    # Order is South, West, North, East
    result = OSMTGC.getOSMData(lower_right_latlon[0], upper_left_latlon[1], upper_left_latlon[0], lower_right_latlon[1])

    # TODO Scale, Sharpen, and Increase Local Constrast for these images to get potentially easier results?
    image_dict = {}
    image_dict["Visible"] = visual
    image_dict["Visible Golf"] = None
    image_dict["Heightmap"] = heightmap
    image_dict["Heightmap Golf"] = None

    fig, ax = plt.subplots()
    plt.title('Move Slider and Press Apply.  Close Window When Happy With Alignment')

    axcolor = 'green'
    plt.subplots_adjust(left=0.3, bottom=0.25)

    axx = plt.axes([0.25, 0.15, 0.65, 0.03], facecolor=axcolor)
    axy = plt.axes([0.25, 0.1, 0.65, 0.03], facecolor=axcolor)
    sx = Slider(axx, 'West/East', -10.0, 10.0, valinit=0.0)
    sy = Slider(axy, 'South/North', -10.0, 10.0, valinit=0.0)

    applyax = plt.axes([0.8, 0.025, 0.1, 0.04])
    button = Button(applyax, 'Apply', color=axcolor, hovercolor='0.975')

    rax = plt.axes([0.05, 0.7, 0.15, 0.15], facecolor=axcolor)
    radio = RadioButtons(rax, image_dict.keys())
    update_image = partial(drawNewImage, ax, image_dict)
    radio.on_clicked(update_image)

    new_offset = partial(drawNewLocation, ax, image_dict, result, image_scale, radio, sx, sy, 1)
    button.on_clicked(new_offset)

    drawNewLocation(ax, image_dict, result, image_scale, radio, None, None, None, None)

    plt.show()

    return (sx.val, sy.val)


if __name__ == "__main__":
    print("main")

    if len(sys.argv) < 2:
        print("Usage: python program.py LAS_DIRECTORY")
        sys.exit(0)
    else:
        lidar_dir_path = sys.argv[1]

    print("Loading data")

    # See if we need to infill.
    hm_file = Path(lidar_dir_path) / 'lidar/heightmap.npy'
    in_file = Path(lidar_dir_path) / 'lidar/infilled.npy'

    if not in_file.exists() or hm_file.stat().st_mtime > in_file.stat().st_mtime:
        print("Filling holes in heightmap")
        # Either infilled doesn't exist or heightmap.npy is newer than infilled
        read_dictionary = np.load(lidar_dir_path + '/lidar/heightmap.npy').item()
        im = read_dictionary['heightmap'].astype('float32')

        mask = cv2.imread(lidar_dir_path + '/lidar/mask.png', cv2.IMREAD_COLOR)

        # Process Image
        out, holeMask = infill_image_scipy(im, mask)

        # Export data
        read_dictionary['heightmap'] = out
        np.save(lidar_dir_path + '/lidar/infilled', read_dictionary) # Save as numpy format since we have raw float elevations
    else:
        read_dictionary = np.load(lidar_dir_path + '/lidar/infilled.npy').item()

    image_scale = read_dictionary["image_scale"]
    intensity_image = read_dictionary['visual']
    heightmap = read_dictionary['heightmap']

    pc = GeoPointCloud()
    pc.addFromImage(heightmap, image_scale, read_dictionary['origin'], read_dictionary['projection'])

    offsets = getManualRegistrationError(intensity_image, heightmap, image_scale, pc)

    print("Feature shift offsets are: " )
    print(offsets)
