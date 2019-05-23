import base64
import cv2
import gzip
import itertools
import json
import math
import numpy as np
import os
from pathlib import Path

def base64GZDecode(data):
    gz_data = base64.b64decode(data)
    return gzip.decompress(gz_data)

def base64GZEncode(data, level):
    gz_data = gzip.compress(data, compresslevel=level)
    return base64.b64encode(gz_data)

def create_directory(course_directory):
    course_dir = Path(course_directory)
    try:
        Path.mkdir(course_dir, mode=0o777)
    except FileExistsError as err:
        pass
    return course_dir

def get_course_file(course_directory):
    # Find the course file
    course_list = list(Path(course_directory).glob('*.course'))
    if not course_list:
        print("No courses found in: " + course_directory)
        return None
    elif len(course_list) > 1:
        print("More than one course found, using " + str(course_list[0]))
    return course_list[0]

def get_course_name(course_directory):
    course_file = get_course_file(course_directory)
    if course_file is None:
        return None
    return course_file.stem

def unpack_course_file(course_directory, course_file=None):
    # Make directory structure
    course_dir = Path(course_directory)
    output_dir = course_dir / 'unpacked'
    description_dir = output_dir / 'course_description'
    metadata_dir = output_dir / 'metadata'
    thumbnail_dir = output_dir / 'thumbnail'

    try:
        Path.mkdir(output_dir, mode=0o777)
        Path.mkdir(description_dir, mode=0o777)
        Path.mkdir(metadata_dir, mode=0o777)
        Path.mkdir(thumbnail_dir, mode=0o777)
    except FileExistsError as err:
        pass

    course_name = ""
    if course_file is None:
        course_file = get_course_file(course_directory)
        course_name = get_course_name(course_directory)

    with gzip.open(str(course_file), 'r') as f:
        file_content = f.read()
        course_json = json.loads(file_content.decode('utf-16'))

        with (output_dir / 'full.json').open('w') as f:
            f.write(file_content.decode('utf-16'))

        course_description64 = course_json["binaryData"]["CourseDescription"]
        thumbnail64 = course_json["binaryData"]["Thumbnail"]
        course_metadata64 = course_json["binaryData"]["CourseMetadata"]

        course_description_json = base64GZDecode(course_description64).decode('utf-16')
        # Remove potential strange unicode characters like u200b
        course_description_json = (course_description_json.encode('ascii', 'ignore')).decode("utf-8")
        with (description_dir / 'course_description.json').open('w') as f:
            f.write(course_description_json)

        thumbnail_json = base64GZDecode(thumbnail64).decode('utf-16')
        # Remove potential strange unicode characters like u200b
        thumbnail_json = (thumbnail_json.encode('ascii', 'ignore')).decode("utf-8")
        t_json = json.loads(thumbnail_json)
        with (thumbnail_dir / 'thumbnail.json').open('w') as f:
            f.write(thumbnail_json)
        thumbnail_jpg = base64.b64decode(t_json["image"])
        with (thumbnail_dir / 'thumbnail.jpg').open('wb') as f:
            f.write(thumbnail_jpg)

        course_metadata_json = base64GZDecode(course_metadata64).decode('utf-16')
        # Remove potential strange unicode characters like u200b
        course_metadata_json = (course_metadata_json.encode('ascii', 'ignore')).decode("utf-8")
        with (metadata_dir / 'course_metadata.json').open('w') as f:
            f.write(course_metadata_json)        

    return course_name

def pack_course_file(course_directory, course_name=None, output_file=None, course_json=None):
    course_dir = Path(course_directory)

    output_path = None
    if output_file is not None:
        output_path = Path(output_file)
    else:
        if course_name is None:
            course_name = get_course_name(course_directory)
            if course_name is None:
                # Nothing found, just use 'output.course'
                course_name = 'output'
        output_path = course_dir / (course_name + '.course')

    print("Saving course as: " + str(output_path))

    # Write out new course description before packing into course
    if course_json is not None:
        write_course_json(course_directory, course_json)

    with (course_dir / 'unpacked/course_description/course_description.json').open('r') as desc:
        with (course_dir / 'unpacked/metadata/course_metadata.json').open('r') as meta:
            with (course_dir / 'unpacked/thumbnail/thumbnail.json').open('r') as thumb:
                desc_read = desc.read()
                meta_read = meta.read()
                thumb_read = thumb.read()
                desc_encoded = base64GZEncode(desc_read.encode('utf-16'), 1).decode('utf-8')
                meta_encoded = base64GZEncode(meta_read.encode('utf-16'), 1).decode('utf-8')
                thumb_encoded = base64GZEncode(thumb_read.encode('utf-16'), 1).decode('utf-8')

                output_json = json.loads('{"data":{},"binaryData":{}}')
                output_json["binaryData"]["CourseDescription"] = desc_encoded
                output_json["binaryData"]["Thumbnail"] = thumb_encoded
                output_json["binaryData"]["CourseMetadata"] = meta_encoded

                # Special dense encoding used for course files
                output_string = json.dumps(output_json, separators=(',', ':'))
 
                # Write to final gz format
                output_gz = gzip.compress(output_string.encode('utf-16'), 1)

                with (output_path).open('wb') as f:
                    f.write(output_gz)
                
                return str(output_path)

def get_course_json(course_directory):
    course_dir = Path(course_directory)
    course_json = ""
    with (course_dir / 'unpacked/course_description/course_description.json').open('r') as f:
        course_json = json.loads(f.read())  
        
    return course_json

def get_metadata_json(course_directory):
    course_dir = Path(course_directory)
    metadata_json = ""
    with (course_dir / 'unpacked/metadata/course_metadata.json').open('r') as f:
        metadata_json = json.loads(f.read())  
        
    return metadata_json

def get_spline_configuration_json(course_directory):
    try:
        course_dir = Path(course_directory)
        spline_json = None
        with (course_dir / 'splines.json').open('r') as f:
            spline_json = json.loads(f.read())  
            
        return spline_json
    except:
        return None

def write_course_json(course_directory, course_json):
    course_dir = Path(course_directory)
    with (course_dir / 'unpacked/course_description/course_description.json').open('w') as f:
        # Reduce floating point resolution to save file space.  Round to millimeter
        # Workaround since dumps has no precision
        # https://stackoverflow.com/questions/1447287/format-floats-with-standard-json-module
        f.write(json.dumps(json.loads(json.dumps(course_json), parse_float=lambda x: round(float(x), 3)), separators=(',', ':')))

def write_metadata_json(course_directory, metadata_json):
    course_dir = Path(course_directory)
    with (course_dir / 'unpacked/metadata/course_metadata.json').open('w') as f:
        out = json.dumps(metadata_json, separators=(',', ':'))
        f.write(out)

def set_course_metadata_name(course_directory, new_course_name):
    metadata_json = get_metadata_json(course_directory)
    metadata_json["name"] = new_course_name
    write_metadata_json(course_directory, metadata_json)

def waypoint_dist(p1, p2):
    dx = p1["x"] - p2["x"]
    dz = p1["z"] - p2["z"]
    return math.sqrt(dx**2 + dz**2)

def get_hole_information(course_json):
    pars = []
    pin_counts = []
    tees = [[],[],[],[],[]]

    for h in course_json["holes"]:
        # Par is same for all tees
        par = h["creatorDefinedPar"]
        if par <= 0: # Check if user specified par
            par = h["par"]
        pars.append(par)

        pin_counts.append(len(h["pinPositions"]))

        # Get common yardage for all tees
        waypoints = h["waypoints"][1:] # Every point but the first point
        common_distance = 0.0
        for i in range(0, len(waypoints)-1):
            common_distance += waypoint_dist(waypoints[i], waypoints[i+1])

        # Get specific yardage for all tees, record total yardage for every possible tee
        for i in range(0, 5):
            if i < len(h["teePositions"]):
                # Convert to yards, from meters
                total_dist = common_distance + waypoint_dist(h["teePositions"][i], waypoints[0])
                tees[i].append(1.09*total_dist)
            else:
                tees[i].append(None)

    return pars, pin_counts, tees


def strip_terrain(course_json, output_file):
    # Copy existing terrain and write to disk
    output_data = {}
    output_data['terrainHeight'] = course_json["userLayers"]["terrainHeight"]
    output_data['height'] = course_json["userLayers"]["height"]

    print("Saving Terrain as " + output_file)
    np.save(output_file, output_data)

    # Clear existing terrain
    course_json["userLayers"]["terrainHeight"] = []
    course_json["userLayers"]["height"] = []

    return course_json

def insert_terrain(course_json, input_file):
    print("Loading terrain from: " + input_file)
    read_dictionary = np.load(input_file).item()

    # Copy existing terrain and write to disk
    course_json["userLayers"]["terrainHeight"] = read_dictionary["terrainHeight"]
    course_json["userLayers"]["height"] = read_dictionary["height"]

    return course_json

def strip_holes(course_json, output_file):
    # Copy existing holes and write to disk
    output_data = {}
    output_data['holes'] = course_json['holes']

    print("Saving Holes as " + output_file)
    np.save(output_file, output_data)

    # Clear existing holes
    course_json['holes'] = []

    return course_json

def insert_holes(course_json, input_file):
    print("Loading holes from: " + input_file)
    read_dictionary = np.load(input_file).item()

    # Replace our holes from those in the file
    course_json['holes'] = read_dictionary['holes']

    return course_json

# Shift terrain and features are separate in case they need to be lined up with each other
def shift_terrain(course_json, easting_shift, northing_shift):
    for i in course_json["userLayers"]["height"]:
        i['position']['x'] += easting_shift
        i['position']['z'] += northing_shift

    for i in course_json["userLayers"]["terrainHeight"]:
        i['position']['x'] += easting_shift
        i['position']['z'] += northing_shift

    return course_json

def shift_features(course_json, easting_shift, northing_shift):
    # Shift splines
    for i in course_json["surfaceSplines"]:
        for wp in i["waypoints"]:
            wp["pointOne"]["x"] += easting_shift
            wp["pointTwo"]["x"] += easting_shift
            wp["waypoint"]["x"] += easting_shift
            wp["pointOne"]["y"] += northing_shift
            wp["pointTwo"]["y"] += northing_shift
            wp["waypoint"]["y"] += northing_shift

    # Shift Holes
    for h in course_json["holes"]:
        for w in h["waypoints"]:
            w["x"] += easting_shift
            w["z"] += northing_shift
        for t in h["teePositions"]:
            t["x"] += easting_shift
            t["z"] += northing_shift
        # Pin positions are in relative coordinates and don't need shifted

    # Shift Brushes
    for b in itertools.chain(course_json["userLayers"]["surfaces"],
                             course_json["userLayers"]["water"],
                             course_json["userLayers"]["outOfBounds"],
                             course_json["userLayers"]["crowdLocations"]):
        b['position']['x'] += easting_shift
        b['position']['z'] += northing_shift

    # Shift Objects
    for o in course_json["placedObjects2"]:
        for i in o["Value"]["items"]:
            i['position']['x'] += easting_shift
            i['position']['z'] += northing_shift

        for c in o["Value"]["clusters"]:
            c['position']['x'] += easting_shift
            c['position']['z'] += northing_shift

    return course_json

def shift_course(course_json, easting_shift, northing_shift):
    course_json = shift_terrain(course_json, easting_shift, northing_shift)
    return shift_features(course_json, easting_shift, northing_shift)

# Helper function to rotate coordinates on many different element types
def rotateCoord(elem, x_key='x', y_key='y', c=1.0, s=0.0):
    x = elem[x_key]
    y = elem[y_key]
    elem[x_key] = x * c - y * s
    elem[y_key] = x * s + y * c

# Rotation angle is positive around the y-DOWN axis
# Positive values will rotate the course clockwise
def rotate_course(course_json, rotation_angle_radians):
    # Elements that have rotation values are stored in degrees
    rotation_angle_degrees = 180.0 * rotation_angle_radians / math.pi

    # Pre calculate cosine and sine with what would be the y-up angle
    c = math.cos(-rotation_angle_radians)
    s = math.sin(-rotation_angle_radians)

    # Rotate Brushes
    for b in itertools.chain(course_json["userLayers"]["height"],
                             course_json["userLayers"]["terrainHeight"],
                             course_json["userLayers"]["surfaces"],
                             course_json["userLayers"]["water"],
                             course_json["userLayers"]["outOfBounds"],
                             course_json["userLayers"]["crowdLocations"]):
        rotateCoord(b['position'], 'x', 'z', c, s)
        b['rotation']['y'] += rotation_angle_degrees

    # Rotate splines
    for i in course_json["surfaceSplines"]:
        for wp in i["waypoints"]:
            rotateCoord(wp["pointOne"], 'x', 'y', c, s)
            rotateCoord(wp["pointTwo"], 'x', 'y', c, s)
            rotateCoord(wp["waypoint"], 'x', 'y', c, s)

    # Rotate Holes
    for h in course_json["holes"]:
        for w in h["waypoints"]:
            rotateCoord(w, 'x', 'z', c, s)
        for t in h["teePositions"]:
            rotateCoord(t, 'x', 'z', c, s)
        for p in h["pinPositions"]:
            # Todo not 100% sure that this is correct
            rotateCoord(p, 'x', 'y', c, s)

    # Rotate Objects
    for o in course_json["placedObjects2"]:
        for i in o["Value"]["items"]:
            rotateCoord(i["position"], 'x', 'z', c, s)
            i['rotation']['y'] += rotation_angle_degrees

        for cl in o["Value"]["clusters"]:
            rotateCoord(cl["position"], 'x', 'z', c, s)
            cl['rotation']['y'] += rotation_angle_degrees

    return course_json

def getCoursePoints(course_json):
    cv2_pts = []

    for i in course_json["userLayers"]["height"]:
        cv2_pts.append([i["position"]["x"], i["position"]["z"]])

    for i in course_json["userLayers"]["terrainHeight"]:
        cv2_pts.append([i["position"]["x"], i["position"]["z"]])

    return cv2_pts

def getBoundingBox(course_json):
    cv2_pts = getCoursePoints(course_json)
    return cv2.boundingRect(np.array(cv2_pts).astype(np.int32))

def getMinBoundingBox(course_json):
    cv2_pts = getCoursePoints(course_json)
    return cv2.minAreaRect(np.array(cv2_pts).astype(np.int32))

def setValues(x, y, ll, ul, ur, lr):
    # r^2 > dist^2, so no need to do square root
    r2 = x**2 + y**2
    if x <= 0.0 and y <= 0.0:
        pdist2 = ll[0]**2 + ll[1]**2
        if r2 > pdist2:
            ll = (x, y, r2)
            return (ll, ul, ur, lr)
    elif x <= 0.0 and y >= 0.0:
        pdist2 = ul[0]**2 + ul[1]**2
        if r2 > pdist2:
            ul = (x, y, r2)
            return (ll, ul, ur, lr)
    elif x >= 0.0 and y >= 0.0:
        pdist2 = ur[0]**2 + ur[1]**2
        if r2 > pdist2:
            ur = (x, y, r2)
            return (ll, ul, ur, lr)
    elif x >= 0.0 and y <= 0.0:
        pdist2 = lr[0]**2 + lr[1]**2
        if r2 > pdist2:
            lr = (x, y, r2)
            return (ll, ul, ur, lr)
    return (ll, ul, ur, lr)

# Assuming terrain always goes further than "other stuff"
# Also assumes course is roughly centered at 0,0
# Returns ll, ul, ur, lr
def get_terrain_extremes(course_json):
    # Initialize to higher/lower values than possible so the first points
    # X, Z, radius_squared to point
    ll = (0.0, 0.0, 0.0)
    ul = (0.0, 0.0, 0.0)
    ur = (0.0, 0.0, 0.0)
    lr = (0.0, 0.0, 0.0)

    for i in course_json["userLayers"]["height"]:
        ll, ul, ur, lr = setValues(i["position"]["x"], i["position"]["z"], ll, ul, ur, lr)

    for i in course_json["userLayers"]["terrainHeight"]:
        ll, ul, ur, lr = setValues(i["position"]["x"], i["position"]["z"], ll, ul, ur, lr)

    return (ll, ul, ur, lr)

# Determines the four extremes and tries to shift and rotate the course to fit within 2000m
def auto_position_course(course_json, printf=print):
    # TODO Corners is redundant with the boundingRect
    extremes = get_terrain_extremes(course_json)
    rect = getBoundingBox(course_json)

    fits_on_map = False

    if -1000.0 <= rect[0] and \
       -1000.0 <= rect[1] and \
       rect[0] + rect[2] <= 1000.0 and \
       rect[1] + rect[3] <= 1000.0:
        fits_on_map = True

    if fits_on_map:
        printf("Course fits within map")

    # If course would fit within 2000x2000, don't try to rotate it
    rotation = 0.0
    if rect[2] > 2000.0 or rect[3] > 2000.0:
        # TODO try cv2.minarearect
        # It seems cool, but doesn't seem to outperform my algorithm

        # Otherwise, need to try to fit this course on the map
        # Rotate to try to maximize the extremes into the corners of the square
        # Can rotate a maximum of 45 degrees and all rotations are equivalent because bounded by a square
        ideal_angles = [-3.0/4.0*math.pi, 3.0/4.0*math.pi, 1.0/4.0*math.pi, -1.0/4.0*math.pi]
        rotation_sum = 0.0
        for c, a in zip(extremes, ideal_angles):
            angle = math.atan2(c[1], c[0])
            angle_diff = abs(a - angle)
            rotation_sum += abs(angle_diff)

        rotation = rotation_sum/float(len(extremes))
        printf("Rotating course by: " + str(rotation))
        course_json = rotate_course(course_json, rotation)

        # See if we needed to rotate the opposite direction
        rect = getBoundingBox(course_json)

        if rect[2] > 2000.0 or rect[3] > 2000.0:
            printf("Trying opposite rotation: " + str(-rotation))
            # Undo our previous rotation and try the other direction
            course_json = rotate_course(course_json, -2.0*rotation)

    # Now see if a translation can help get the full course on
    rect = getBoundingBox(course_json)

    eastwest_shift = -rect[2] / 2 - rect[0]
    northsouth_shift = -rect[3] / 2 - rect[1]

    printf("Shift course by: " + str(eastwest_shift) + " x " + str(northsouth_shift))

    return shift_course(course_json, eastwest_shift, northsouth_shift)

# This doesn't work perfectly, but it works for many courses
def auto_merge_courses(course1_json, course2_json):
    # Shift and rotate courses so that they don't overlap
    # Get bounding boxes for each course
    bb1 = getMinBoundingBox(course1_json)
    bb2 = getMinBoundingBox(course2_json)

    # Find which course is larger
    larger_course = course1_json
    smaller_course = course2_json
    if bb2[1][0] + bb2[1][1] > bb1[1][0] + bb1[1][1]:
        larger_course = course2_json
        smaller_course = course1_json

    # Fit the larger course section on any way we can
    larger_course = auto_position_course(larger_course)

    # Find enough space for the smaller course on the map
    bb1 = getMinBoundingBox(larger_course)
    bb2 = getMinBoundingBox(smaller_course)

    # Rotate smaller course to match larger course
    larger_horizontal_aligned = bb1[1][1] > bb1[1][0]
    smaller_horizontal_aligned = bb2[1][1] > bb2[1][0]
    rotation_angle = (bb1[2] - bb2[2])*math.pi/180.0
    if larger_horizontal_aligned == smaller_horizontal_aligned:
        rotation_angle += math.pi/2.0 # Rotate an extra 90 to align major distance
    rotate_course(smaller_course, rotation_angle)

    # Shift courses to not overlap
    bb1 = getMinBoundingBox(larger_course)
    bb2 = getMinBoundingBox(smaller_course)

    # Determine dominant angle for larger course
    # Needed because minAreaRect only reports -90 to 0.0
    rotation = 0.0
    radius = 0.0 # (h0/2 + gap + h1/2)
    orig_angle = math.pi/180.0*bb1[2]
    if bb1[1][0] > bb1[1][1]: # height > width
        radius = (bb1[1][0]/2.0 + 20 + bb2[1][0]/2.0)
        if orig_angle < -75:
            rotation = 0.0 # Shift straight right
        else:
            rotation = math.pi/4.0 # Shift at 45 degrees to upper right
    else:
        radius = (bb1[1][1]/2.0 + 20 + bb2[1][1]/2.0)
        if orig_angle < -75:
            rotation = math.pi/2.0 # Shift up
        else:
            rotation = 3.0*math.pi/4.0 # Shift at 45 degrees to upper left

    # x0 + radius * sin/cos(rotation)
    # Angles are -90 to 0.0, invert so courses shift up or to the right
    new_center_x = bb1[0][0] + radius*math.cos(rotation)
    new_center_y = bb1[0][1] + radius*math.sin(rotation)
    offset_x = new_center_x - bb2[0][0]
    offset_y = new_center_y - bb2[0][1]
    smaller_course = shift_course(smaller_course, offset_x, offset_y)

    # Apply usual merge
    merged_course = merge_courses(course1_json, course2_json)

    # Position this combined course as best as possible
    return auto_position_course(merged_course)

def merge_courses(course1_json, course2_json):
    for i in course2_json["userLayers"]["height"]:
        course1_json["userLayers"]["height"].append(i)

    for i in course2_json["userLayers"]["terrainHeight"]:
        course1_json["userLayers"]["terrainHeight"].append(i)

    for i in course2_json["surfaceSplines"]:
        course1_json["surfaceSplines"].append(i)

    for i in course2_json["userLayers"]["surfaces"]:
        course1_json["userLayers"]["surfaces"].append(i)

    for i in course2_json["userLayers"]["water"]:
        course1_json["userLayers"]["water"].append(i)

    for i in course2_json["userLayers"]["outOfBounds"]:
        course1_json["userLayers"]["outOfBounds"].append(i)

    for i in course2_json["userLayers"]["crowdLocations"]:
        course1_json["userLayers"]["crowdLocations"].append(i)

    for i in course2_json["placedObjects2"]:
        course1_json["placedObjects2"].append(i)

    print("Warning, holes may be out of order")
    for i in course2_json["holes"]:
        # Can only support 18 holes per course
        if len(course1_json["holes"]) < 18:
            course1_json["holes"].append(i)
        else:
            print("Too many holes")

    return course1_json


def elevate_terrain(course_json, elevate_shift, buffer_height=10.0, clip_lowest_value=-2.0, printf=print):
    # Automatic terrain shift
    if elevate_shift == 0.0 or elevate_shift == None:
        elevations = []
        for i in course_json["userLayers"]["height"]:
            elevations.append(i['value'])

        remaining_terrain = json.loads('[]')
        for i in course_json["userLayers"]["terrainHeight"]:
            elevations.append(i['value'])

        elevations = np.array(elevations)

        # Remove lower outliers
        # The idea is to sort the points by elevation
        # Then take the gradient (difference between each point)
        # Valid points will have many neighbors close in height to them
        s = np.sort(elevations)
        g = np.gradient(s)

        # Find the point in the curve where elevation stabilizes
        # Only need to look in the first half of the data.  Keep noisy positive elevation points
        # 0.05 is an approximate threshold.  Most data is less than 0.015 in elevation difference at the valid point
        half_length = round(len(elevations)/2)
        diff_threshold = (np.median(g[0:half_length]) + g[0:half_length].max(axis=0))/2.0
        diff_threshold = min(0.015, diff_threshold) # Don't set too low if course is very consistent
        try:
            split_index = np.where(g[0:half_length] > diff_threshold)[0][-1] # where returns a tuple of arrays?
            split_index += 1 # Move one past the last invalid point
       
            # The lowest valid point will be our new zero
            elevate_shift = -min(s[split_index:]) + buffer_height
        except IndexError:
            printf("Course likely does not need elevation adjustment")
            return course_json

    printf("Shifting elevation by: " + str(elevate_shift))

    remaining_height = json.loads('[]')
    for i in course_json["userLayers"]["height"]:
        value = i['value']
        if value + elevate_shift >= clip_lowest_value:
            i['value'] += elevate_shift
            remaining_height.append(i)
    course_json["userLayers"]["height"] = remaining_height

    remaining_terrain = json.loads('[]')
    for i in course_json["userLayers"]["terrainHeight"]:
        value = i['value']
        if value + elevate_shift >= clip_lowest_value:
            i['value'] += elevate_shift
            remaining_terrain.append(i)
    course_json["userLayers"]["terrainHeight"] = remaining_terrain

    return course_json

# Maximum course size is 2000 meters by 2000 meters.
# This crops if anything is further than max from the origin
# 2000.0 / 2 is 1000.0 meters
def crop_course(course_json, max_easting=1000.0, max_northing=1000.0):
    # Filter elevation
    remaining_height = json.loads('[]')
    for i in course_json["userLayers"]["height"]:
        if abs(i["position"]["x"]) <= max_easting and \
           abs(i["position"]["z"]) <= max_northing:
            remaining_height.append(i)
    course_json["userLayers"]["height"] = remaining_height

    remaining_terrain = json.loads('[]')
    for i in course_json["userLayers"]["terrainHeight"]:
        if abs(i["position"]["x"]) <= max_easting and \
           abs(i["position"]["z"]) <= max_northing:
            remaining_terrain.append(i)
    course_json["userLayers"]["terrainHeight"] = remaining_terrain

    # Filter splines
    remaining_splines = json.loads('[]')
    for i in course_json["surfaceSplines"]:
        keep_spline = True
        for wp in i["waypoints"]:
            if abs(wp["pointOne"]["x"]) <= max_easting and \
               abs(wp["pointTwo"]["x"]) <= max_easting and \
               abs(wp["waypoint"]["x"]) <= max_easting and \
               abs(wp["pointOne"]["y"]) <= max_northing and \
               abs(wp["pointTwo"]["y"]) <= max_northing and \
               abs(wp["waypoint"]["y"]) <= max_northing:
               continue
            else:
                keep_spline = False
                break

        if keep_spline:
            remaining_splines.append(i)
    course_json["surfaceSplines"] = remaining_splines

    # Filter Holes
    remaining_holes = json.loads('[]')
    for h in course_json["holes"]:
        keep_hole = True
        for w in h["waypoints"]:
            if abs(w["x"]) <= max_easting and \
               abs(w["z"]) <= max_northing:
               continue
            else:
                keep_hole = False
                break
 
        if keep_hole:
            for t in h["teePositions"]:
                if abs(t["x"]) <= max_easting and \
                   abs(t["z"]) <= max_northing:
                    continue
                else:
                    keep_hole = False
                    break

        if keep_hole:
            remaining_holes.append(h)
    course_json["holes"] = remaining_holes

    return course_json
