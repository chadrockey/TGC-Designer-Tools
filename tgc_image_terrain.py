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

def get_pixel(x_pos, z_pos, height, scale):
    output = json.loads('{"tool":0,"position":{"x":0.0,"y":"-Infinity","z":0.0},"rotation":{"x":0.0,"y":0.0,"z":0.0},"_orientation":0.0,"scale":{"x":1.0, \
                         "y":1.0,"z":1.0},"type":72,"value":0.0,"holeId":-1,"radius":0.0,"orientation":0.0}')
    output['position']['x'] = x_pos
    output['position']['z'] = z_pos
    output['value'] = height
    output['scale']['x'] = scale
    output['scale']['z'] = scale
    return output

# Set various constants that we need
def set_constants(course_json):
    # None of these have been proven necessary, but it works best to start with a clean slate
    course_json["flattenFairways"] = False # Needed to not flatten under fairway splines
    course_json["flattenGreens"] = False # Needed to not flatten under green splines

    # Add our own JSON element so the courses could be filtered easily
    course_json["gis"] = "ChadRockeyDevelopment"

    return course_json

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
    # Turn mask into matrix order from image order
    mask = np.flip(mask, 0)

    # Process Image
    out, holeMask = infill_image_scipy(im, mask)

    # Export data
    read_dictionary['heightmap'] = out
    np.save(lidar_dir_path + '/lidar/infilled', read_dictionary) # Save as numpy format since we have raw float elevations
else:
    read_dictionary = np.load(lidar_dir_path + '/lidar/infilled.npy').item()

pc = GeoPointCloud()
image_scale = read_dictionary['image_scale']
pc.addFromImage(read_dictionary['heightmap'], image_scale, read_dictionary['origin'], read_dictionary['projection'])

print("Unpacking course files")
course_name = tgc_tools.unpack_course_file(lidar_dir_path)
if course_name is None:
    print("Could not find a .course file in " + lidar_dir_path)
    sys.exit(0)

print("Generating course files")
course_json = ""
with open(lidar_dir_path + "/unpacked/course_description/course_description.json", 'r') as f:
    course_json = json.loads(f.read())

    # Clear existing terrain
    course_json = set_constants(course_json)
    course_json["userLayers"]["height"] = []
    course_json["userLayers"]["terrainHeight"] = []

    # Get lowest height and subtract off some amount with a buffer?
    adjustment = 0.0 #min_value

    print("Adjustment to height is: " + str(adjustment))

    # Convert the pointcloud into height elements
    num_points = len(pc.points())
    progress_interval = int(num_points / 25)
    for n, i in enumerate(pc.points()):
        if n % progress_interval == 0:
            print(str(int(100.0*float(n) / num_points)) + "% through pointcloud")

        x, y, z = pc.enuToTGC(i[0], i[1], 0.0) # Don't transform y, it's inverted from elevation
        course_json["userLayers"]["height"].append(get_pixel(x, z, i[2] - adjustment, image_scale))

    # Download OpenStreetMaps Data for this smaller area
    print("Adding golf features to lidar data")
    # Use this data to create playable courses automatically
    upper_left_enu = pc.ulENU()
    lower_right_enu = pc.lrENU()
    upper_left_latlon = pc.enuToLatLon(*upper_left_enu)
    lower_right_latlon = pc.enuToLatLon(*lower_right_enu)
    # Order is South, West, North, East
    result = OSMTGC.getOSMData(lower_right_latlon[0], upper_left_latlon[1], upper_left_latlon[0], lower_right_latlon[1])
    OSMTGC.addOSMToTGC(course_json, pc, result.ways)

    # Automatically adjust course elevation
    print("Moving course to lowest valid elevaiton")
    course_json = tgc_tools.elevate_terrain(course_json, None)

    # Automatic rotate to fit if needed
    print("Adjusting course to fit on map")
    course_json = tgc_tools.auto_position_course(course_json)

with open(lidar_dir_path + "/unpacked/course_description/course_description.json", 'w') as f:
    out = json.dumps(course_json, separators=(',', ':'))
    f.write(out)

print("Packing course files")
final_file = tgc_tools.pack_course_file(lidar_dir_path, course_name)
print("Saved completed course to: " + final_file)
