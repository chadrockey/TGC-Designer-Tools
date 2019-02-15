import cv2
import json
import math
import matplotlib.pyplot as plt
import numpy as np
import overpy
import sys

from GeoPointCloud import GeoPointCloud
import tgc_definitions
import tgc_tools

def drawBrushesOnImage(brushes, color, im, pc, image_scale, fill=True):
    for brush in brushes:
        center = pc.tgcToCV2(brush["position"]["x"], brush["position"]["z"], image_scale)
        center = (center[1], center[0]) # In point coordinates, not pixel
        width = brush["scale"]["x"] / image_scale
        height = brush["scale"]["z"] / image_scale
        rotation = - brush["rotation"]["y"] # Inverted degrees, cv2 bounding_box uses degrees

        thickness = 4
        if fill:
            thickness = -1 # Negative thickness is a filled ellipse

        brush_type_name = tgc_definitions.brushes.get(int(brush["type"]), "unknown")

        if 'square' in brush_type_name:
            box_points = cv2.boxPoints((center, (2.0*width, 2.0*height), rotation)) # Squares seem to be larger than circles
            box_points = np.int32([box_points]) # Bug with fillPoly, needs explict cast to 32bit

            if fill:
                cv2.fillPoly(im, box_points, color, lineType=cv2.LINE_AA)
            else:
                cv2.polylines(im, box_points, True, color, thickness, lineType=cv2.LINE_AA)
        else: # Draw as ellipse for now
            '''center – The rectangle mass center.
            size – Width and height of the rectangle.
            angle – The rotation angle in a clockwise direction. When the angle is 0, 90, 180, 270 etc., the rectangle becomes an up-right rectangle.'''
            bounding_box =  (center, (1.414*width, 1.414*height), rotation) # Circles seem to scale according to radius
            cv2.ellipse(im, bounding_box, color, thickness=thickness, lineType=cv2.LINE_AA)  

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
            cv2.fillPoly(im, nds, color, lineType=cv2.LINE_AA)
        else:
            cv2.polylines(im, nds, s["isClosed"], color, thickness, lineType=cv2.LINE_AA)

def drawObjectsOnImage(objects, color, im, pc, image_scale):
    for ob in objects:
        for item in ob["Value"]["items"]:
            # Assuming all items are ellipses for now
            center = pc.tgcToCV2(item["position"]["x"], item["position"]["z"], image_scale)
            center = (center[1], center[0]) # In point coordinates, not pixel
            width = max(item["scale"]["x"] / image_scale, 8.0)
            height = max(item["scale"]["z"] / image_scale, 8.0)
            rotation = - item["rotation"]["y"] * math.pi / 180.0 # Inverted degrees, cv2 uses clockwise radians

            '''center – The rectangle mass center.
            size – Width and height of the rectangle.
            angle – The rotation angle in a clockwise direction. When the angle is 0, 90, 180, 270 etc., the rectangle becomes an up-right rectangle.'''

            bounding_box_of_ellipse =  (center, (width, height), rotation)

            cv2.ellipse(im, bounding_box_of_ellipse, color, thickness=-1, lineType=cv2.LINE_AA)

        for cluster in ob["Value"]["clusters"]:
            # Assuming all items are ellipses for now
            center = pc.tgcToCV2(cluster["position"]["x"], cluster["position"]["z"], image_scale)
            center = (center[1], center[0]) # In point coordinates, not pixel
            width = cluster["radius"] / image_scale
            height = cluster["radius"] / image_scale
            rotation = - cluster["rotation"]["y"] * math.pi / 180.0 # Inverted degrees, cv2 uses clockwise radians

            '''center – The rectangle mass center.
            size – Width and height of the rectangle.
            angle – The rotation angle in a clockwise direction. When the angle is 0, 90, 180, 270 etc., the rectangle becomes an up-right rectangle.'''

            bounding_box_of_ellipse =  (center, (width, height), rotation)

            cv2.ellipse(im, bounding_box_of_ellipse, color, thickness=-1, lineType=cv2.LINE_AA)

def drawHolesOnImage(holes, color, im, pc, image_scale):
    for h in holes:
        # Get the shape of this spline and draw it on the image
        waypoints = []
        for wp in h["waypoints"]:
            waypoints.append(pc.tgcToCV2(wp["x"], wp["z"], image_scale))

        tees = []
        for t in h["teePositions"]:
            tees.append(pc.tgcToCV2(t["x"], t["z"], image_scale))

        # Going to skip drawing pinPositions due to low resolution

        # Uses points and not image pixels, so flip the x and y
        waypoints = np.array(waypoints)
        waypoints[:,[0, 1]] = waypoints[:,[1, 0]]
        tees = np.array(tees)
        tees[:,[0, 1]] = tees[:,[1, 0]]

        # Draw a line between each waypoint
        thickness = 5
        for i in range(0, len(waypoints)-1):
            first_point = tuple(waypoints[i])
            second_point = tuple(waypoints[i+1])
            cv2.line(im, first_point, second_point, color, thickness=thickness, lineType=cv2.LINE_AA)

        # Draw a line between each tee and the second waypoint
        first_waypoint = tuple(waypoints[1])
        for tee in tees:
            t = tuple(tee)
            cv2.line(im, t, first_waypoint, color, thickness=thickness, lineType=cv2.LINE_AA)


def drawCourseAsImage(course_json):
    im = np.zeros((2000, 2000, 3), np.float32) # Courses are 2000m x 2000m
    image_scale = 1.0 # Draw one pixel per meter
    pc = GeoPointCloud()
    pc.width = 2000.0
    pc.height = 2000.0

    # Draw terrain first
    drawBrushesOnImage(course_json["userLayers"]["terrainHeight"], (0.35, 0.2, 0.0), im, pc, image_scale)

    drawBrushesOnImage(course_json["userLayers"]["height"], (0.5, 0.2755, 0.106), im, pc, image_scale)

    # Next draw surfaces in correct stacking orders
    uls = course_json["userLayers"]["surfaces"]
    ss = course_json["surfaceSplines"]

    # Draw real water
    water_color = (0.1, 0.2, 0.5)
    drawBrushesOnImage(course_json["userLayers"]["water"], water_color, im, pc, image_scale)

    # Mulch/Water Visualization Surface #2 has low priority, so draw it first
    # Drawing as the black/dark blue, but it will show up different depending on scene
    surface2_color = (0.1, 0.2, 0.25)
    drawSplinesOnImage([s for s in ss if s["surface"] == 8], surface2_color, im, pc, image_scale)
    drawBrushesOnImage([b for b in uls if b["surfaceCategory"] == 8], surface2_color, im, pc, image_scale)

    # Then draw heavy rough
    heavy_rough_color = (0, 0.3, 0.1)
    drawSplinesOnImage([s for s in ss if s["surface"] == 4], heavy_rough_color, im, pc, image_scale)
    drawBrushesOnImage([b for b in uls if b["surfaceCategory"] == 4], heavy_rough_color, im, pc, image_scale)

    # Then draw rough
    rough_color = (0.1, 0.35, 0.15)
    drawSplinesOnImage([s for s in ss if s["surface"] == 3], rough_color, im, pc, image_scale)
    drawBrushesOnImage([b for b in uls if b["surfaceCategory"] == 3], rough_color, im, pc, image_scale)

    # Next draw fairways
    fairway_color = (0, 0.75, 0.2)
    drawSplinesOnImage([s for s in ss if s["surface"] == 2], fairway_color, im, pc, image_scale)
    drawBrushesOnImage([b for b in uls if b["surfaceCategory"] == 2], fairway_color, im, pc, image_scale)

    # Next draw greens
    green_color = (0, 1.0, 0.2)
    drawSplinesOnImage([s for s in ss if s["surface"] == 1], green_color, im, pc, image_scale) 
    drawBrushesOnImage([b for b in uls if b["surfaceCategory"] == 1], green_color, im, pc, image_scale)

    # Next draw bunkers
    bunker_color = (0.85, 0.85, 0.7)
    drawSplinesOnImage([s for s in ss if s["surface"] == 0], bunker_color, im, pc, image_scale)
    drawBrushesOnImage([b for b in uls if b["surfaceCategory"] == 0], bunker_color, im, pc, image_scale)

    # Surface #1 - Gravel?
    surface1_color = (0.7, 0.7, 0.7)
    drawSplinesOnImage([s for s in ss if s["surface"] == 7], surface1_color, im, pc, image_scale)
    drawBrushesOnImage([b for b in uls if b["surfaceCategory"] == 7], surface1_color, im, pc, image_scale)

    # Surface #3 Cart Path
    cart_path_color = (0.3, 0.3, 0.3)
    drawSplinesOnImage([s for s in ss if s["surface"] == 10], cart_path_color, im, pc, image_scale)
    drawBrushesOnImage([b for b in uls if b["surfaceCategory"] == 10], cart_path_color, im, pc, image_scale)

    # Don't draw brush or surface 5 because this is are clear generated trees
    # Don't draw brush or surface 6 because this is clear generated objects

    # Draw out of bounds as white boundaries
    out_of_bounds_color = (1.0, 1.0, 1.0)
    drawBrushesOnImage(course_json["userLayers"]["outOfBounds"], out_of_bounds_color, im, pc, image_scale, fill=False)

    # Draw crowds as pink boundaries
    crowd_color = (1.0, 0.4, 0.75)
    drawBrushesOnImage(course_json["userLayers"]["crowdLocations"], crowd_color, im, pc, image_scale, fill=False)

    # Draw objects last in yellow
    object_color = (0.95, 0.9, 0.2)
    drawObjectsOnImage(course_json["placedObjects2"], object_color, im, pc, image_scale)

    # Last draw holes themselves
    hole_color = (0.9, 0.3, 0.2)
    drawHolesOnImage(course_json["holes"], hole_color, im, pc, image_scale)

    return im

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
