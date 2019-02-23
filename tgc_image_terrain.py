import cv2
import json
import math
import numpy as np
from pathlib import Path
import random
import sys
import time

from GeoPointCloud import GeoPointCloud
from infill_image import infill_image_scipy
import OSMTGC
import tgc_tools

status_print_duration = 1.0 # Print progress every n seconds

def get_pixel(x_pos, z_pos, height, scale, brush_type=72):
    output = json.loads('{"tool":0,"position":{"x":0.0,"y":"-Infinity","z":0.0},"rotation":{"x":0.0,"y":0.0,"z":0.0},"_orientation":0.0,"scale":{"x":1.0, \
                         "y":1.0,"z":1.0},"type":0,"value":0.0,"holeId":-1,"radius":0.0,"orientation":0.0}')
    output['type'] = brush_type
    output['position']['x'] = x_pos
    output['position']['z'] = z_pos
    output['value'] = height
    output['scale']['x'] = scale
    output['scale']['z'] = scale
    return output

def get_object_item(x_pos, z_pos):
    output = json.loads('{"position":{"x":0.0,"y":"-Infinity","z":0.0},"rotation":{"x":0.0,"y":0.0,"z":0.0},"scale":{"x":1.0,"y":1.0,"z":1.0}}')
    output['position']['x'] = x_pos
    output['position']['z'] = z_pos
    output['rotation']['y'] = random.randrange(0, 359)
    return output

def get_placed_object(object_type):
    output = json.loads('{"Key":{"category":0,"type":0,"theme":true},"Value":{"items":[],"clusters":[]}}')
    output['Key']['type'] = object_type
    return output

def get_trees(trees, pc, image_scale):
    output = []

    # Just set all trees as default tree for now
    normal_trees = get_placed_object(0)
    #palm_trees = get_placed_object(10)

    min_radius_scale = 0.2
    radius_scale_range = 1.5 - min_radius_scale
    min_height_scale = 0.5
    height_scale_range = 1.2 - min_height_scale

    min_tree_radius = min(trees, key=lambda x: x[2])[2]
    max_tree_radius = max(trees, key=lambda x: x[2])[2]
    tree_radius_range = max_tree_radius - min_tree_radius
    radius_multiplier = radius_scale_range / tree_radius_range
    min_tree_height = min(trees, key=lambda x: x[3])[3]
    max_tree_height = max(trees, key=lambda x: x[3])[3]
    tree_height_range = max_tree_height - min_tree_height
    height_multiplier = height_scale_range / tree_height_range
    for tree in trees:
        easting, northing, r, h = tree
        x, y, z = pc.projToTGC(easting, northing, 0.0)
        t = get_object_item(x, z)
        # Don't scale sizes for now
        if False: #r < 2.0:  
            #t['scale']['y'] = h / 20.0
            palm_trees['Value']['items'].append(t)
        else:
            t['scale']['y'] = (h-min_tree_height)*height_multiplier + min_height_scale
            t['scale']['x'] = (r-min_tree_radius)*radius_multiplier + min_radius_scale
            t['scale']['z'] = (r-min_tree_radius)*radius_multiplier + min_radius_scale
            normal_trees['Value']['items'].append(t)

    output.append(normal_trees)
    #output.append(palm_trees)
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

    # Infill data to prevent holes and make the data nice and smooth
    hm_file = Path(heightmap_dir_path) / '/heightmap.npy'
    try:
        read_dictionary = np.load(heightmap_dir_path + '/heightmap.npy').item()
        im = read_dictionary['heightmap'].astype('float32')

        mask = cv2.imread(heightmap_dir_path + '/mask.png', cv2.IMREAD_COLOR)
        # Turn mask into matrix order from image order
        mask = np.flip(mask, 0)

        # Process Image
        printf("Filling holes in heightmap")
        image_scale = read_dictionary['image_scale']
        printf("Map scale is: " + str(image_scale) + " meters")
        background_ratio = None
        if options_dict.get('add_background', False):
            background_scale = float(options_dict.get('background_scale', 16.0))
            background_ratio = background_scale/image_scale
            printf("Background requested with scale: " + str(background_scale) + " meters")
            
        heightmap, background, holeMask = infill_image_scipy(im, mask, background_ratio=background_ratio, printf=printf)
    except FileNotFoundError:
        printf("Could not find heightmap or mask at: " + heightmap_dir_path)
        return course_json

    # Clear existing terrain
    course_json = set_constants(course_json, options_dict.get('flatten_fairways', False), options_dict.get('flatten_greens', False))
    course_json["userLayers"]["height"] = []
    course_json["userLayers"]["terrainHeight"] = []
    course_json["placedObjects2"] = []

    # Construct high resolution model
    pc = GeoPointCloud()
    pc.addFromImage(heightmap, image_scale, read_dictionary['origin'], read_dictionary['projection'])

    # Add low resolution background
    if background is not None:
        background_pc = GeoPointCloud()
        background_pc.addFromImage(background, background_scale, read_dictionary['origin'], read_dictionary['projection'])
        num_points = len(background_pc.points())
        last_print_time = time.time()

        for n, i in enumerate(background_pc.points()):
            if time.time() > last_print_time + status_print_duration:
                last_print_time = time.time()
                printf(str(round(100.0*float(n) / num_points, 2)) + "% through heightmap")

            # Convert to projected coordinates, then project to TGC using the high resolution pointcloud to ensure alignment
            easting, northing = background_pc.enuToProj(i[0], i[1])
            x, y, z = pc.projToTGC(easting, northing, 0.0)
            # Using 10 - the very soft circles means we need to scale 2.5x more to fill and smooth the terrain
            course_json["userLayers"]["height"].append(get_pixel(x, z, i[2], 2.5*background_scale, brush_type=10))

    # Convert the pointcloud into height elements
    num_points = len(pc.points())
    last_print_time = time.time()
    for n, i in enumerate(pc.points()):
        if time.time() > last_print_time + status_print_duration:
            last_print_time = time.time()
            printf(str(round(100.0*float(n) / num_points, 2)) + "% through heightmap")

        x, y, z = pc.enuToTGC(i[0], i[1], 0.0) # Don't transform y, it's inverted from elevation
        course_json["userLayers"]["height"].append(get_pixel(x, z, i[2], image_scale))

    if len(read_dictionary['trees']) > 0:
        printf("Adding trees")
        for o in get_trees(read_dictionary['trees'], pc, image_scale):
            course_json["placedObjects2"].append(o)

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
