import cv2
import xml.etree.ElementTree as ET
from GeoPointCloud import GeoPointCloud
import json
import math
import numpy as np
import overpy

import tgc_definitions

# Returns left, top, right, bottom
def nodeBoundingBox(nds):
    X = [nd[0] for nd in nds]
    #Y = [nd[1] for nd in nds]
    Z = [nd[2] for nd in nds]
    return (min(X), max(Z), max(X), min(Z))

def shapeCenter(nds):
    bb = nodeBoundingBox(nds)
    return ((bb[0] + bb[2])/2.0, (bb[1]+bb[3])/2.0)

def getwaypoint(easting, vertical, northing):
    output = json.loads('{"pointOne": {"x": 0.0,"y": 0.0},"pointTwo": {"x": 0.0,"y": 0.0},"waypoint": {"x": 0.0,"y": 0.0} }')
    output["waypoint"]["x"] = easting
    output["waypoint"]["y"] = northing
    return output

def getwaypoint3D(x, y, z):
    wp = json.loads('{"x": 0.0,"y": 0.0,"z": 0.0}')
    wp["x"] = x
    wp["y"] = y
    wp["z"] = z
    return wp

def getTangentAngle(previous_point, next_point):
    return math.atan2(float(next_point["y"])-float(previous_point["y"]), float(next_point["x"])-float(previous_point["x"]))

def completeSpline(points, spline_json, handle_length=1.0, is_clockwise=True, tight_splines=True):
    number_points = len(spline_json["waypoints"])
    for i in range(0, number_points):
        prev_index = i - 1 # Works for negative
        next_index = i + 1
        if next_index == number_points:
            next_index = 0

        p = spline_json["waypoints"][prev_index]["waypoint"]
        t = spline_json["waypoints"][i]["waypoint"]
        n = spline_json["waypoints"][next_index]["waypoint"]

        # Just guessing what these points are and if they are important
        # Set point one and point two to be on the line between the previous and next point, but centered on this point
        angle = getTangentAngle(p, n)
        if tight_splines:
            # Pull the spline handles perpendicular and inside the shape in order to accurately
            # represent the shapes downloaded online.  Don't want a lot of expansion or smoothing
            angle_one = angle - 1.1 * math.pi / 2.0
            angle_two = angle - 0.9 * math.pi / 2.0

            # Clockwise splines appear to point inward by default, this is what we want
            if not is_clockwise:
                # Flip handles inwards
                angle_temp = angle_one
                angle_one = angle_two + math.pi
                angle_two = angle_temp + math.pi
        else:
            # Loose, smooth splines
            angle_one = angle + math.pi
            angle_two = angle

        # TODO Use angle to center to guarantee these point inwards?  I see them pointing out sometimes
        spline_json["waypoints"][i]["pointOne"]["x"] = t["x"] + handle_length * math.cos(angle_one)
        spline_json["waypoints"][i]["pointOne"]["y"] = t["y"] + handle_length * math.sin(angle_one)
        spline_json["waypoints"][i]["pointTwo"]["x"] = t["x"] + handle_length * math.cos(angle_two)
        spline_json["waypoints"][i]["pointTwo"]["y"] = t["y"] + handle_length * math.sin(angle_two)

def splineIsClockWise(spline_json):
    # https://stackoverflow.com/questions/1165647/how-to-determine-if-a-list-of-polygon-points-are-in-clockwise-order
    points = spline_json["waypoints"]
    edge_sum = 0.0
    for i in range(0, len(points)):
        edge_sum += (points[i]["waypoint"]["x"]-points[i-1]["waypoint"]["x"])*(points[i]["waypoint"]["y"]+points[i-1]["waypoint"]["y"])

    return edge_sum >= 0.0

def shrinkSplineNormals(spline_json, shrink_distance=1.0, is_clockwise=True):
    if not shrink_distance:
        return spline_json

    number_points = len(spline_json["waypoints"])
    for i in range(0, number_points):
        prev_index = i - 1 # Works for negative
        next_index = i + 1
        if next_index == number_points:
            next_index = 0

        p = spline_json["waypoints"][prev_index]["waypoint"]
        t = spline_json["waypoints"][i]["waypoint"]
        n = spline_json["waypoints"][next_index]["waypoint"]
        tangent_angle = getTangentAngle(p, n)
        # Move the spline points along the normal to the inside of the shape
        # Since the game expands splines by a fixed amount, we need to shrink the shape by a set amount
        normal_angle = tangent_angle - math.pi/2.0
        # Clockwise splines appear to point inward by default, this is what we want
        if not is_clockwise:
            # Flip normal inwards
            normal_angle = normal_angle + math.pi

        # Now shift the spline point by shrink_distance in the direction of normal_angle
        t["x"] += math.cos(normal_angle)*shrink_distance
        t["y"] += math.sin(normal_angle)*shrink_distance

    return spline_json

def newSpline(points, path_width=0.01, shrink_distance=None, handle_length=0.5, tight_splines=True):
    spline = json.loads('{"surface": 1, \
            "secondarySurface": 11, \
            "secondaryWidth": -1.0, \
            "waypoints": [], \
            "width": 0.01, \
            "state": 3, \
            "ClosedPath": false, \
            "isClosed": true, \
            "isFilled": true \
        }')
    spline["width"] = path_width

    for p in points:
        spline["waypoints"].append(getwaypoint(*p))

    # Determine direction of spline
    is_clockwise = splineIsClockWise(spline)

    # Reduce spline normal distance (move points inwards) by half of width
    # This compensates for the game treating all splines like filled cartpaths
    if shrink_distance is None:
        shrink_distance = path_width/2.0
    spline = shrinkSplineNormals(spline, shrink_distance=shrink_distance, is_clockwise=is_clockwise)

    # Now that spline is shrunk, set the handles according to the properties we want
    completeSpline(points, spline, handle_length=handle_length, is_clockwise=is_clockwise, tight_splines=tight_splines)

    return spline

def newBunker(points):
    # Very tight shaped to make complex curves
    bunker = newSpline(points, path_width = 0.01, handle_length=1.0, tight_splines=True)
    bunker["surface"] = tgc_definitions.featuresToSurfaces["bunker"]
    bunker["secondarySurface"] = tgc_definitions.featuresToSurfaces["heavyrough"]
    bunker["secondaryWidth"] = 2.5
    return bunker

def newGreen(points):
    green = newSpline(points, path_width = 1.7, handle_length=0.2, tight_splines=True)
    green["surface"] = tgc_definitions.featuresToSurfaces["green"]
    green["secondarySurface"] = tgc_definitions.featuresToSurfaces["heavyrough"]
    green["secondaryWidth"] = 2.5
    return green

def newTeeBox(points):
    teebox = newSpline(points, path_width = 1.7, handle_length=0.2, tight_splines=True)
    teebox["surface"] = tgc_definitions.featuresToSurfaces["green"]
    teebox["secondarySurface"] = tgc_definitions.featuresToSurfaces["heavyrough"]
    teebox["secondaryWidth"] = 2.5
    return teebox

def newFairway(points):
    fw = newSpline(points, path_width = 3.0, handle_length=3.0, tight_splines=False)
    fw["surface"] = tgc_definitions.featuresToSurfaces["fairway"]
    fw["secondarySurface"] = tgc_definitions.featuresToSurfaces["rough"]
    fw["secondaryWidth"] = 5.0
    return fw

def newRough(points):
    rh = newSpline(points, path_width = 1.7, handle_length=3.0, tight_splines=False)
    # Game outputs secondary as 1
    # Remove with 0 width
    rh["surface"] = tgc_definitions.featuresToSurfaces["rough"]
    rh["secondarySurface"] = 1
    rh["secondaryWidth"] = 0.0
    return rh

def newHeavyRough(points):
    hr = newSpline(points, path_width = 1.7, handle_length=3.0, tight_splines=False)
    # Game outputs secondary as 1
    # Remove with 0 width
    hr["surface"] = tgc_definitions.featuresToSurfaces["heavyrough"]
    hr["secondarySurface"] = 1
    hr["secondaryWidth"] = 0.0
    return hr

def newCartPath(points, area=False):
    path_width = 2.0
    shrink_distance = 0.0
    if area:
        shrink_distance = path_width/2.0
    cp = newSpline(points, path_width=path_width, shrink_distance=shrink_distance, handle_length=4.0, tight_splines=False) # Smooth a lot
    # Cartpath is surface 10 (this is the one with Cartpath logo in Designer)
    # Remove secondary with 0 width
    cp["surface"] = tgc_definitions.featuresToSurfaces["cartpath"] # Cartpath, Surface #3
    cp["secondarySurface"] = 11
    cp["secondaryWidth"] = 0.0
    # 0 is 'not closed' and 3 is 'closed and filled' maybe a bitmask?
    if area:
        cp["state"] = 3
        cp["isClosed"] = True
        cp["isFilled"] = True
    else:
        cp["state"] = 0 # Todo figure out what this means
        cp["isClosed"] = False
        cp["isFilled"] = False

    return cp

def newWalkingPath(points, area=False):
    # Minimum width that will render in meters
    path_width = 1.7
    shrink_distance = 0.0
    if area:
        shrink_distance = path_width/2.0
    wp = newSpline(points, path_width=path_width, shrink_distance=shrink_distance, handle_length=2.0, tight_splines=False)
    # Make walking paths Surface #1 for visibility
    # User can switch to green/fairway/rough depending on taste
    # Remove secondary with 0 width
    wp["surface"] = tgc_definitions.featuresToSurfaces["surface1"]
    wp["secondarySurface"] = tgc_definitions.featuresToSurfaces["rough"]
    wp["secondaryWidth"] = 0.0
    if area:
        wp["state"] = 3
        wp["isClosed"] = True
        wp["isFilled"] = True
    else:
        wp["state"] = 0 # Todo figure out what this means
        wp["isClosed"] = False
        wp["isFilled"] = False
    return wp

def newWaterHazard(points):
    # Add placeholder for water hazard.
    # Add spline and fill with black mulch
    # No width, only very detailed fill shape
    wh = newSpline(points, path_width = 0.01, handle_length=0.2, tight_splines=True)
    # Fill as mulch/surface #2 as a placeholder
    wh["surface"] = tgc_definitions.featuresToSurfaces["surface2"]
    wh["secondarySurface"] = 11
    wh["secondaryWidth"] = 0.0
    return wh

def addHalfwayPoint(points):
    first = points[0]
    last = points[-1]
    new_point = ((first[0] + last[0])/2.0, (first[1]+last[1])/2.0, (first[2]+last[2])/2.0)

    return (first, new_point, last)

def newHole(userpar, points):
    hole = json.loads('{"waypoints": [], "teePositions": [],"pinPositions": [{"x": 0.0,"y": 0.0,"z": 0.0}],"greenRadius": 0.0,"teeRadius": 0.0,"fairwayRadius": 0.0, \
            "fairwayStart": 0.0,"fairwayEnd": 0.0,"fairwayNoiseScale": -1.0,"roughRadius": 0.0,"heavyRoughRadius": 0.0,"hazardGreenCount": 0.0,"hazardFairwayCount": 0.0, \
            "hazardFairwayPeriod": -1.0,"teeHeight": -1.0, "greenSeed": 206208328, "fairwaySeed": 351286870,"teeTexture": -1, \
            "creatorDefinedPar": -1, "name": "","flagOffset": {"x": 0.0,"y": 0.0},"par": 4}')

    hole["creatorDefinedPar"] = userpar

    if len(points) < 2: # Minimum needed points
        return None
    if len(points) == 2: # Need to set an aiming point halfway between
        points = addHalfwayPoint(points)

    for p in points:
        hole["waypoints"].append(getwaypoint3D(p[0], 0.0, p[2]))

    hole["teePositions"].append(getwaypoint3D(points[0][0], 0.0, points[0][2]))

    return hole

def getOSMData(bottom_lat, left_lon, top_lat, right_lon, printf=print):
    op = overpy.Overpass()
    # Order is South, West, North, East
    coord_string = str(bottom_lat) + "," + str(left_lon) + "," + str(top_lat) + "," + str(right_lon)
    query = "(node(" + coord_string + ");way(" + coord_string + "););out;"
    printf("OpenStreetMap Overpass query: " + query)
    return op.query(query) # Request both nodes and ways for the region of interest using a union

def clearFeatures(course_json):
    # Clear splines?  Make this optional
    course_json["surfaceSplines"] = []
    # Game will crash if more than 18 holes found, so always clear holes
    course_json["holes"] = []
    return course_json

def addOSMToTGC(course_json, geopointcloud, ways, x_offset=0.0, y_offset=0.0, options_dict={}, printf=print):
    # Ways represent features composed of many lat/long points (nodes)
    # We can convert these directly into the game's splines

    # Get terrain bounding box
    ul_enu = geopointcloud.ulENU()
    lr_enu = geopointcloud.lrENU()
    ul_tgc = geopointcloud.enuToTGC(*ul_enu, 0.0)
    lr_tgc = geopointcloud.enuToTGC(*lr_enu, 0.0)

    course_json = clearFeatures(course_json)

    hole_dictionary = dict() # Holes must be ordered by hole_num.  Must keep track of return order just in case data doesn't have hole number
    for way in ways:
        golf_type = way.tags.get("golf", None)
        area = False
        try:
            area = "yes" == way.tags.get("area", None)
        except:
            pass
        if golf_type is not None:
            # Get the shape of this way and draw it as a poly
            nds = []
            for node in way.get_nodes(resolve_missing=True): # Allow automatically resolving missing nodes, but this is VERY slow with the API requests, try to request beforehand
                nds.append(geopointcloud.latlonToTGC(node.lat, node.lon, x_offset, y_offset))

            # Check this shapes bounding box against the limits of the terrain, don't draw outside this bounds
            # Left, Top, Right, Bottom
            nbb = nodeBoundingBox(nds)
            if nbb[0] < ul_tgc[0] or nbb[1] > ul_tgc[2] or nbb[2] > lr_tgc[0] or nbb[3] < lr_tgc[2]:
                printf("Golf element : " + golf_type + " is off of map, skipping...")
                continue

            if golf_type == "green" and options_dict.get('green', True):
                course_json["surfaceSplines"].append(newGreen(nds))
            elif golf_type == "bunker" and options_dict.get('bunker', True):
                course_json["surfaceSplines"].append(newBunker(nds))
            elif golf_type == "tee" and options_dict.get('teebox', True):
                course_json["surfaceSplines"].append(newTeeBox(nds))
            elif golf_type == "fairway" and options_dict.get('fairway', True):
                course_json["surfaceSplines"].append(newFairway(nds))
            elif golf_type == "driving_range" and options_dict.get('range', True):
                # Add as fairway
                course_json["surfaceSplines"].append(newFairway(nds))
            elif golf_type == "rough" and options_dict.get('rough', True):
                course_json["surfaceSplines"].append(newRough(nds))
            elif (golf_type == "water_hazard" or golf_type == "lateral_water_hazard") and options_dict.get('water', True):
                course_json["surfaceSplines"].append(newWaterHazard(nds))
            elif golf_type == "cartpath" and options_dict.get('cartpath', True):
                course_json["surfaceSplines"].append(newCartPath(nds, area=area))
            elif golf_type == "path" and options_dict.get('path', True):
                course_json["surfaceSplines"].append(newWalkingPath(nds, area=area))
            elif golf_type == "hole" and options_dict.get('hole', True):
                par = int(way.tags.get("par", -1))
                hole_num = int(way.tags.get("ref", -1))
                hole = newHole(par, nds)
                if hole is not None:
                    if hole_num == 0:
                        hole_num = len(hole_dictionary) + 1
                    hole_dictionary[hole_num] = hole
            else:
                printf("Skipping: " + golf_type)

    # Insert all the found holes
    for key in sorted(hole_dictionary):
        course_json["holes"].append(hole_dictionary[key])

def addOSMFromXML(course_json, xml_data, options_dict={}, printf=print):
    printf("Adding OpenStreetMap from XML")
    op = overpy.Overpass()
    result = op.parse_xml(xml_data)

    printf("Determining the UTM Geo Projection for this area")
    # Find the lat and lon bounding box from the XML directly
    # Can't find the query bounds in overpy
    root = ET.fromstring(xml_data)
    for bounds in root.iter('bounds'):
        latmin = float(bounds.get('minlat'))
        latmax = float(bounds.get('maxlat'))
        lonmin = float(bounds.get('minlon'))
        lonmax = float(bounds.get('maxlon'))
        break
    
    # Create a basic geopointcloud to handle this projection
    pc = GeoPointCloud()
    pc.addFromLatLon((latmin, lonmin), (latmax, lonmax), printf=printf)

    addOSMToTGC(course_json, pc, result.ways, x_offset=float(options_dict.get('adjust_ew', 0.0)), y_offset=float(options_dict.get('adjust_ns', 0.0)), \
                options_dict=options_dict, printf=printf)

    return course_json

def drawWayOnImage(way, color, im, pc, image_scale, x_offset=0.0, y_offset=0.0):
    # Get the shape of this way and draw it as a poly
    nds = []
    for node in way.get_nodes(resolve_missing=True): # Allow automatically resolving missing nodes, but this is VERY slow with the API requests, try to request them above instead
        nds.append(pc.latlonToCV2(node.lat, node.lon, image_scale, x_offset, y_offset))
    # Uses points and not image pixels, so flip the x and y
    nds = np.array(nds)
    nds[:,[0, 1]] = nds[:,[1, 0]]
    nds = np.int32([nds]) # Bug with fillPoly, needs explict cast to 32bit
    cv2.fillPoly(im, nds, color) 

def addOSMToImage(ways, im, pc, image_scale, x_offset=0.0, y_offset=0.0, printf=print):
    for way in ways:
        golf_type = way.tags.get("golf", None)
        if golf_type is not None:
            # Default to green
            color = (0, 0.75, 0.2)
            if golf_type == "green":
                color = (0, 1.0, 0.2)
            elif golf_type == "tee":
                color = (0, 0.8, 0)
            elif golf_type == "water_hazard":
                color = (0, 0, 1.0)
            elif golf_type == "fairway":
                color = color
            else:
                continue

            drawWayOnImage(way, color, im, pc, image_scale, x_offset, y_offset)

    # Draw bunkers last on top of all other layers as a hack until proper layer order is established here
    # Needed for things like bunkers in greens...  :\
    for way in ways:
        golf_type = way.tags.get("golf", None)
        if golf_type == "bunker":
            color = (0.85, 0.85, 0.7)
            drawWayOnImage(way, color, im, pc, image_scale, x_offset, y_offset)

    return im
