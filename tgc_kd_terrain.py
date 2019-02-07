import base64
import gzip
import json
import math
import os

from PIL import Image
import PIL

import matplotlib.pyplot as plt
import matplotlib.image as mpimg

import numpy as np

import scipy.spatial as spatial

from statistics import median

# Using kd tree directly on laspy points
'''
# Open a file in read mode:
inFile = laspy.file.File("./laspytest/data/simple.las")
# Grab a numpy dataset of our clustering dimensions:
dataset = np.vstack([inFile.X, inFile.Y, inFile.Z]).transpose()
# Build the KD Tree
tree = scipy.spatial.kdtree(data)
# This should do the same as the FLANN example above, though it might
# be a little slower.
tree.query(dataset[100,], k = 5)
'''

scale = 2.0
rotation = -0.785398/2.0
level = 18

# Adjust all values so the lowest value is 5cm above the water line
adjustment = 16.77

def pixelsToPosition(i, j, w, h, scale, angle):
    x_pos = i + (1.0 - float(w))/2.0
    y_pos = j + (1.0 - float(h))/2.0
    x_scaled = scale*x_pos
    y_scaled = -scale*y_pos # Negative due to different import coordinates
    x_rot = x_scaled * math.cos(angle) + y_scaled * math.sin(angle)
    y_rot = y_scaled * math.cos(angle) - x_scaled * math.sin(angle)
    return (x_rot, y_rot)

im = Image.open("infilled.tiff")
#im = Image.new("F", (width, height), 0.0)

width = im.width
height = im.height

#imgplot = plt.imshow(im)

min_z, max_z = im.getextrema()

#plt.show()

print("Generating course files")

print("Building KDTree")

input_list = []
for j in range(0, height):
    for i in range(0, width):
        elevation = im.getpixel((i,j))
        if elevation >= 0.0:
            input_list.append([i, j, elevation])

input_data = np.array(input_list)

# "terrainHeight":[{"tool":0,"position":{"x":0.0,"y":"-Infinity","z":0.0},"rotation":{"x":0.0,"y":0.0,"z":0.0},"_orientation":0.0,"scale":{"x":8000.0,"y":1.0,"z":8000.0},"type":72,"value":1.31901169,"holeId":-1,"radius":0.0,"orientation":0.0},
#{"tool":1,"position":{"x":13.6078491,"y":"-Infinity","z":-233.6012},"rotation":{"x":0.0,"y":0.0,"z":0.0},"_orientation":0.0,"scale":{"x":1.0,"y":1.0,"z":1.0},"type":73,"value":0.9181293,"holeId":-1,"radius":0.0,"orientation":0.0}

def get_pixel(x_pos, z_pos, height, x_scale, z_scale, rotation):
    x_scale = 2 * x_scale
    z_scale = 2 * z_scale
    output = '{"tool":0,"position":{"x":'
    output = output + "{:.1f}".format(x_pos)
    #print("{:.1f}".format(x_pos))
    output = output + ',"y":"-Infinity","z":'
    output = output + "{:.1f}".format(z_pos)
    output = output + '},"rotation":{"x":0.0,"y":'
    output = output + "{:.1f}".format(-rotation)
    output = output + ',"z":0.0},"_orientation":0.0,"scale":{"x":'
    output = output + "{:.3f}".format(x_scale)
    output = output + ',"y":1.0,"z":'
    output = output + "{:.3f}".format(z_scale)
    output = output + '},"type":10,"value":'
    output = output + "{:.3f}".format(height)
    output = output + ',"holeId":-1,"radius":0.0,"orientation":0.0}'
    return json.loads(output)

def accumulate_z(node, z_list):
    if hasattr(node, 'idx'):
        z_list.append(input_data[node.idx[0]][2])
        return
    accumulate_z(node.less, z_list)
    accumulate_z(node.greater, z_list)

def median_z(node):
    z_list = []
    accumulate_z(node, z_list)
    return median(z_list)


def draw_rectangle(node, depth, mins, maxes, course_json, scale, rotation):
    """Recursively plot a visualization of the KD tree region"""
    x1 = mins[0]
    y = mins[1]
    h = maxes[1] - y
    x = mins[0]
    w = maxes[0] - x
    y1 = mins[1]
    z_avg = (mins[2] + maxes[2])/2.0 # Todo improve this by looking at the children values?

    if not hasattr(node, 'split'):
        # Is a leaf node, draw this no matter what
        # Set leaf node size to one, so this is a single pixel?
        pixel = input_data[node.idx[0]]
        if pixel[2] > 0.1:
            x_pos, y_pos = pixelsToPosition(pixel[0]+(scale*1.0)/2.0, pixel[1]-(scale*1.0)/2.0, im.width, im.height, scale, rotation)
            #course_json["userLayers"][terrainHeight"].append(get_pixel(x_pos+(scale*w)/2.0, y_pos-(scale*h)/2.0, pixel[2] - adjustment, scale*w, scale*h))
            course_json["userLayers"]["terrainHeight"].append(get_pixel(x_pos, y_pos, pixel[2] - adjustment, scale*1.0, scale*1.0, rotation))
        return

    w1 = node.split - x1
    x2 = node.split
    h1 = node.split - y1
    y2 = node.split
    w2 = maxes[0] - x2
    h2 = maxes[1] - y2

    # End of depth traversal
    if depth == 0:
        z_avg = median_z(node);
        if node.split_dim == 0: # Divide along x
            if z_avg > 0.1:
                x_pos, y_pos = pixelsToPosition(x1+(scale*w1)/2.0, y-(scale*h)/2.0, im.width, im.height, scale, rotation)
                course_json["userLayers"]["terrainHeight"].append(get_pixel(x_pos, y_pos, z_avg - adjustment, scale*w1, scale*h, rotation))
            #ax.add_patch(get_rect(x1, y, w1, h, z_color))
            if z_avg > 0.1:
                x_pos, y_pos = pixelsToPosition(x2+(scale*w2)/2.0, y-(scale*h)/2.0, im.width, im.height, scale, rotation)
                course_json["userLayers"]["terrainHeight"].append(get_pixel(x_pos, y_pos, z_avg - adjustment, scale*w2, scale*h, rotation))
            #ax.add_patch(get_rect(x2, y, w2, h, z_color))
            #rect = plt.Rectangle((x1, y), w1, h, ec='red', fc='none')
            #ax.add_patch(rect)

            #rect2 = plt.Rectangle((x2, y), w2, h, ec='red', fc='none')
            #ax.add_patch(rect2)
        elif node.split_dim == 1: # Divide along y
            if z_avg > 0.1:
                x_pos, y_pos = pixelsToPosition(x+(scale*w)/2.0, y1-(scale*h1)/2.0, im.width, im.height, scale, rotation)
                course_json["userLayers"]["terrainHeight"].append(get_pixel(x_pos, y_pos, z_avg - adjustment, scale*w, scale*h1, rotation))
            #ax.add_patch(get_rect(x, y1, w, h1, z_color))
            if z_avg > 0.1:
                x_pos, y_pos = pixelsToPosition(x+(scale*w)/2.0, y2-(scale*h2)/2.0, im.width, im.height, scale, rotation)
                course_json["userLayers"]["terrainHeight"].append(get_pixel(x_pos, y_pos, z_avg - adjustment, scale*w, scale*h2, rotation))
            #ax.add_patch(get_rect(x, y2, w, h2, z_color))
            #rect = plt.Rectangle((x, y1), w, h1, ec='red', fc='none')
            #ax.add_patch(rect)

            #rect2 = plt.Rectangle((x, y2), w, h2, ec='red', fc='none')
            #ax.add_patch(rect2)
        else:
            if z_avg > 0.1:
                #print("z split???")
                x_pos, y_pos = pixelsToPosition(x+(scale*w)/2.0, y-(scale*h)/2.0, im.width, im.height, scale, rotation)
                course_json["userLayers"]["terrainHeight"].append(get_pixel(x_pos, y_pos, z_avg - adjustment, scale*w, scale*h, rotation))
            #ax.add_patch(get_rect(x, y, w, h, z_color))
            # Along z, draw full xy rectangle
            #rect = plt.Rectangle((x, y), w, h, ec='red', fc='none')
            #ax.add_patch(rect)

        return

    if node.less is not None:
        if node.split_dim is not 2: # Don't print lower if splitting on z?
            new_max = [maxes[0], maxes[1], maxes[2]]
            new_max[node.split_dim] = node.split
            draw_rectangle(node.less, depth-1, mins, new_max, course_json, scale, rotation)

    if node.greater is not None:
        new_min = [mins[0], mins[1], mins[2]]
        new_min[node.split_dim] = node.split
        draw_rectangle(node.greater, depth-1, new_min, maxes, course_json, scale, rotation)

tree = spatial.KDTree(input_data, leafsize=1)



course_json = ""
with open("flat/course_description/course_description.json", 'r') as f:
    course_json = json.loads(f.read())

    flatten_all = json.loads('{"tool":0,"position":{"x":0.0,"y":"-Infinity","z":0.0},"rotation":{"x":0.0,"y":0.0,"z":0.0},"_orientation":0.0,"scale":{"x":8000.0,"y":1.0,"z":8000.0},"type":72,"value":1.0,"holeId":-1,"radius":0.0,"orientation":0.0}')
    raise_all = json.loads('{"tool":1,"position":{"x":0.0,"y":"-Infinity","z":0.0},"rotation":{"x":0.0,"y":0.0,"z":0.0},"_orientation":0.0,"scale":{"x":8000.0,"y":1.0,"z":8000.0},"type":72,"value":30.0,"holeId":-1,"radius":0.0,"orientation":0.0}')

    # Flatten course first
    course_json["userLayers"]["terrainHeight"] = [flatten_all]
    #course_json["userLayers"]["terrainHeight"].append(raise_all)

    # Get lowest height and subtract off some amount with a buffer?
    height_list = list(im.getdata())

    min_value = min(i for i in height_list if i > 10.0)

    print("Adjustment to height is: " + str(adjustment))

    print("Building from tree")

    draw_rectangle(tree.tree, level, tree.mins, tree.maxes, course_json, scale, rotation)

    # Set pattern into landscape
    #for x in range(-400, 401, 1):
    #    print(str(x))
    #    for y in range(-400,401, 1):
    #        height = 20.0 + 15.0 * math.cos(math.sqrt(float(x)*float(x)+float(y)*float(y))/(6.28 * 5.0))
    #        course_json["userLayers"]["terrainHeight"].append(get_pixel(x, y, height))

with open("flat/course_description/course_description.json", 'w') as f:
    out = json.dumps(course_json, separators=(',', ':'))
    f.write(out)
    '''f = open(output_dir + '/full.json', 'w')
    f.write(file_content.decode('utf-16'))

    course_description64 = course_json["binaryData"]["CourseDescription"]
    thumbnail64 = course_json["binaryData"]["Thumbnail"]
    course_metadata64 = course_json["binaryData"]["CourseMetadata"]

    course_description_json = base64GZDecode(course_description64).decode('utf-16')
    f = open(description_dir + '/course_description.json', 'w')
    f.write(course_description_json)

    thumbnail_json = base64GZDecode(thumbnail64).decode('utf-16')
    t_json = json.loads(thumbnail_json)
    f = open(thumbnail_dir + '/thumbnail.json', 'w')
    f.write(thumbnail_json)
    thumbnail_jpg = base64.b64decode(t_json["image"])
    open(thumbnail_dir + '/thumbnail.jpg', 'wb').write(thumbnail_jpg)

    course_metadata_json = base64GZDecode(course_metadata64).decode('utf-16')
    print(course_metadata_json)
    f = open(metadata_dir + '/course_metadata.json', 'w')
    f.write(course_metadata_json)'''

    #decoded = base64.b64decode(file_content)
    #print(decoded)