import cv2
import json
import math
import matplotlib.pyplot as plt
import numpy as np
import overpy
import sys

from GeoPointCloud import GeoPointCloud
import tgc_tools

def drawBrushOnImage(brush, color, im, pc, image_scale):
    # Assuming tool is circular brush for now
    center = pc.tgcToCV2(brush["position"]["x"], brush["position"]["z"], image_scale)
    center = (center[1], center[0]) # In point coordinates, not pixel
    width = brush["scale"]["x"] / image_scale
    height = brush["scale"]["z"] / image_scale
    rotation = - brush["rotation"]["y"] * math.pi / 180.0 # Inverted degrees, cv2 uses clockwise radians

    '''center – The rectangle mass center.
    size – Width and height of the rectangle.
    angle – The rotation angle in a clockwise direction. When the angle is 0, 90, 180, 270 etc., the rectangle becomes an up-right rectangle.'''

    bounding_box_of_ellipse =  (center, (width, height), rotation)

    cv2.ellipse(im, bounding_box_of_ellipse, color, thickness=-1)  # Negative thickness is a filled ellipse

def drawSplinesOnImage(splines, color, im, pc, image_scale):
    for s in splines:
        # Get the shape of this spline and draw it on the image
        nds = []
        for wp in s["waypoints"]:
            nds.append(pc.tgcToCV2(wp["waypoint"]["x"], wp["waypoint"]["y"], image_scale))

        # Uses points and not image pixels, so flip the x and y
        nds = np.array(nds)
        nds[:,[0, 1]] = nds[:,[1, 0]]
        nds = np.int32([nds]) # Bug with fillPoly, needs explict cast to 32bit

        thickness = int(s["width"])
        if(thickness < image_scale):
            thickness = int(image_scale)

        if s["isFilled"]:
            cv2.fillPoly(im, nds, color)
        else:
            cv2.polylines(im, nds, s["isClosed"], color, thickness)

def processTerrain(course_json, im, pc, image_scale):
    th = course_json["userLayers"]["terrainHeight"]
    h = course_json["userLayers"]["height"]

    for b in th:
        drawBrushOnImage(b, (0.5, 0.25, 0.0), im, pc, image_scale)

    for b in h:
        drawBrushOnImage(b, (0.5, 0.2755, 0.106), im, pc, image_scale)

def processSplines(course_json, im, pc, image_scale):
    ss = course_json["surfaceSplines"]

    # First draw heavy rough
    drawSplinesOnImage([s for s in ss if s["surface"] == 4], (0, 0.3, 0.1), im, pc, image_scale)

    # Then draw rough
    drawSplinesOnImage([s for s in ss if s["surface"] == 3], (0, 0.3, 0.1), im, pc, image_scale)

    # Next draw fairways
    drawSplinesOnImage([s for s in ss if s["surface"] == 2], (0, 0.75, 0.2), im, pc, image_scale) 

    # Next draw greens
    drawSplinesOnImage([s for s in ss if s["surface"] == 1], (0, 1.0, 0.2), im, pc, image_scale) 

    # Next draw bunkers
    drawSplinesOnImage([s for s in ss if s["surface"] == 0], (0.85, 0.85, 0.7), im, pc, image_scale) 

    # Next draw everything else in a cart-path like texture
    drawSplinesOnImage([s for s in ss if s["surface"] not in [0, 1, 2, 3, 4]], (0.6, 0.6, 0.6), im, pc, image_scale) 

def drawCourseAsImage(course_json):
    im = np.zeros((2000, 2000, 3), np.float32) # Courses are 2000m x 2000m
    image_scale = 1.0 # Draw one pixel per meter
    pc = GeoPointCloud()
    pc.width = 2000.0
    pc.height = 2000.0

    processTerrain(course_json, im, pc, image_scale)
    processSplines(course_json, im, pc, image_scale)

    return im

'''def getCourseBoundingBox(course_json, draw_box=True):
    im = drawCourseAsImage(course_json)

    ret,thresh = cv2.threshold(cv2.cvtColor(255*im, cv2.COLOR_RGB2GRAY).astype(np.uint8),10,255,0)

    #thresh = thresh.astype(np.int32)

    contours,hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = contours[0]

    print(cnt)

    rect = cv2.minAreaRect(cnt)
    print(rect)
    box = cv2.boxPoints(rect)
    box = np.int0(box)
    cv2.drawContours(im,[box],0,(0,0,255),2)
    plt.show()

    if draw_box:
        fig = plt.figure()
        plt.imshow(im, origin='lower')
        plt.show()

    return box'''

if __name__ == "__main__":
    print("main")

    if len(sys.argv) < 2:
        print("Usage: python program.py COURSE_DIRECTORY")
        sys.exit(0)
    else:
        lidar_dir_path = sys.argv[1]

    print("Loading course file")
    course_json = tgc_tools.get_course_json(lidar_dir_path)

    im = drawCourseAsImage(course_json)

    fig = plt.figure()

    plt.imshow(im, origin='lower')

    plt.show()

    #getCourseBoundingBox(course_json)
