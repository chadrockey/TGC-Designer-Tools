import cv2
import json
import math
import numpy as np
from pathlib import Path
import sys
import time

from GeoPointCloud import GeoPointCloud
from infill_image import infill_image_scipy
import OSMTGC
import tgc_tools

status_print_duration = 1.0 # Print progress every n seconds

def get_pixel(x_pos, z_pos, height, scale):
    output = json.loads('{"tool":0,"position":{"x":0.0,"y":"-Infinity","z":0.0},"rotation":{"x":0.0,"y":0.0,"z":0.0},"_orientation":0.0,"scale":{"x":1.0, \
                         "y":1.0,"z":1.0},"type":0,"value":0.0,"holeId":-1,"radius":0.0,"orientation":0.0}')
    output['type'] = 72 # Which brush shape to use
    output['position']['x'] = x_pos
    output['position']['z'] = z_pos
    output['value'] = height
    output['scale']['x'] = scale
    output['scale']['z'] = scale
    return output

# Set various constants that we need
def set_constants(course_json, flatten_fairways=False, flatten_greens=False):
    # None of these have been proven necessary, but it works best to start with a clean slate
    course_json["flattenFairways"] = flatten_fairways # Needed to not flatten under fairway splines
    course_json["flattenGreens"] = flatten_greens # Needed to not flatten under green splines

    # Add our own JSON element so the courses could be filtered easily
    # Am choosing an organization name so that TGC-Desinger-Tools could be forked
    course_json["gis"] = "ChadRockeyDevelopment"

    return course_json

def generate_course(course_json, heightmap_dir_path, options_dict={}, printf=print):
    printf("Loading data from " + heightmap_dir_path)

    # See if we need to infill.
    hm_file = Path(heightmap_dir_path) / '/heightmap.npy'
    in_file = Path(heightmap_dir_path) / '/infilled.npy'

    if not in_file.exists() or hm_file.stat().st_mtime > in_file.stat().st_mtime:
        # Either infilled doesn't exist or heightmap.npy is newer than infilled
        try:
            read_dictionary = np.load(heightmap_dir_path + '/heightmap.npy').item()
            im = read_dictionary['heightmap'].astype('float32')

            mask = cv2.imread(heightmap_dir_path + '/mask.png', cv2.IMREAD_COLOR)
            # Turn mask into matrix order from image order
            mask = np.flip(mask, 0)

            # Process Image
            printf("Filling holes in heightmap")
            out, holeMask = infill_image_scipy(im, mask)
        except:
            printf("Could not find heightmap or mask at: " + heightmap_dir_path)
            return course_json

        # Export data
        read_dictionary['heightmap'] = out
        np.save(heightmap_dir_path + '/infilled', read_dictionary) # Save as numpy format since we have raw float elevations
    else:
        read_dictionary = np.load(heightmap_dir_path + '/infilled.npy').item()

    pc = GeoPointCloud()
    image_scale = read_dictionary['image_scale']
    pc.addFromImage(read_dictionary['heightmap'], image_scale, read_dictionary['origin'], read_dictionary['projection'])

    # Clear existing terrain
    course_json = set_constants(course_json, options_dict.get('flatten_fairways', False), options_dict.get('flatten_greens', False))
    course_json["userLayers"]["height"] = []
    course_json["userLayers"]["terrainHeight"] = []

    # Convert the pointcloud into height elements
    num_points = len(pc.points())
    last_print_time = 0.0
    for n, i in enumerate(pc.points()):
        if time.time() > last_print_time + status_print_duration:
            last_print_time = time.time()
            printf(str(round(100.0*float(n) / num_points, 2)) + "% through heightmap")

        x, y, z = pc.enuToTGC(i[0], i[1], 0.0) # Don't transform y, it's inverted from elevation
        course_json["userLayers"]["height"].append(get_pixel(x, z, i[2], image_scale))

    # Download OpenStreetMaps Data for this smaller area
    if options_dict.get('use_osm', True):
        printf("Adding golf features to lidar data")
        # Use this data to create playable courses automatically
        upper_left_enu = pc.ulENU()
        lower_right_enu = pc.lrENU()
        upper_left_latlon = pc.enuToLatLon(*upper_left_enu)
        lower_right_latlon = pc.enuToLatLon(*lower_right_enu)
        # Order is South, West, North, East
        result = OSMTGC.getOSMData(lower_right_latlon[0], upper_left_latlon[1], upper_left_latlon[0], lower_right_latlon[1], printf=printf)
        OSMTGC.addOSMToTGC(course_json, pc, result.ways, x_offset=float(options_dict.get('adjust_ew', 0.0)), y_offset=float(options_dict.get('adjust_ns', 0.0)), \
                                                         options_dict=options_dict, printf=printf)

    # Automatically adjust course elevation
    if options_dict.get('auto_elevation', True):
        printf("Moving course to lowest valid elevation")
        course_json = tgc_tools.elevate_terrain(course_json, None, printf=printf)

    # Automatic rotate to fit if needed
    if options_dict.get('auto_position', True):
        printf("Adjusting course to fit on map")
        course_json = tgc_tools.auto_position_course(course_json, printf=printf)

    printf("Course Description Complete")

    return course_json

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python program.py COURSE_DIRECTORY HEIGHTMAP_DIRECTORY")
        sys.exit(0)
    else:
        course_dir_path = sys.argv[1]
        heightmap_dir_path = sys.argv[2]

    print("Getting course description")
    course_json = tgc_tools.get_course_json(course_dir_path)

    print("Generating course")
    course_json = generate_course(course_json, heightmap_dir_path)

    print("Saving new course description")
    tgc_tools.write_course_json(course_dir_path, course_json)
