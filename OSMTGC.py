import cv2
import json
import math
import numpy as np
import overpy

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

def completeSpline(points, spline_json, handle_length):
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
        angle = math.atan2(float(n["y"])-float(p["y"]), float(n["x"])-float(p["x"]))
        # Pull the spline handles perpendicular and inside the shape in order to accurately
        # represent the shapes downloaded online.  Don't want a lot of expansion or smoothing
        angle_one = angle - 1.1 * math.pi / 2.0
        angle_two = angle - 0.9 * math.pi / 2.0

        # TODO Use angle to center to guarantee these point inwards?  I see them pointing out sometimes

        spline_json["waypoints"][i]["pointOne"]["x"] = t["x"] + handle_length * math.cos(angle_one)
        spline_json["waypoints"][i]["pointOne"]["y"] = t["y"] + handle_length * math.sin(angle_one)
        spline_json["waypoints"][i]["pointTwo"]["x"] = t["x"] + handle_length * math.cos(angle_two)
        spline_json["waypoints"][i]["pointTwo"]["y"] = t["y"] + handle_length * math.sin(angle_two)

def newSpline(points, handle_length):
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

    for p in points:
        spline["waypoints"].append(getwaypoint(*p))

    completeSpline(points, spline, handle_length)

    return spline

def newGreen(points):
    green = newSpline(points, 0.2)

    # Green is surface 1
    # Add secondarySurface 11
    green["surface"] = 1
    green["secondarySurface"] = 11
    green["secondaryWidth"] = 0.4
    return green

def newBunker(points):
    bunker = newSpline(points, 1.0)

    # Bunker is surface 0
    # Add secondarySurface 4
    # Also set a default secondary width
    bunker["surface"] = 0
    bunker["secondarySurface"] = 4
    bunker["secondaryWidth"] = 0.3
    return bunker

def newTeeBox(points):
    teebox = newSpline(points, 0.2) # Smooth Teeboxes a lot

    # Teebox uses Green Surface? 1
    # Add secondarySurface 11 ? 
    teebox["surface"] = 1
    teebox["secondarySurface"] = 11
    teebox["secondaryWidth"] = 0.5
    return teebox

def newFairway(points):
    fw = newSpline(points, 0.2)

    # Fairway is surface 2
    # Add secondarySurface 3
    # Also set a default secondary width
    fw["surface"] = 2
    fw["secondarySurface"] = 3
    fw["secondaryWidth"] = 6.48058176
    return fw

def newRough(points):
    rh = newSpline(points, 0.2)

    # Rough is surface 3
    # Going to be really nice and not make this heavy rough (4)
    # Game outputs secondary as 1
    # Remove with 0 width
    rh["surface"] = 3
    rh["secondarySurface"] = 1
    rh["secondaryWidth"] = 0.0
    return rh

def newWaterHazard(points):
    # Add placeholder for water hazard.
    # Add spline and fill with black mulch
    wh = newSpline(points, 0.2)

    # Rough is surface 3
    # Going to be really nice and not make this heavy rough (4)
    # Game outputs secondary as 1
    # Remove with 0 width
    wh["surface"] = 8
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

def addOSMToTGC(course_json, geopointcloud, ways, x_offset=0.0, y_offset=0.0, printf=print):
    # Ways represent features composed of many lat/long points (nodes)
    # We can convert these directly into the game's splines

    # Get terrain bounding box
    ul_enu = geopointcloud.ulENU()
    lr_enu = geopointcloud.lrENU()
    ul_tgc = geopointcloud.enuToTGC(*ul_enu, 0.0)
    lr_tgc = geopointcloud.enuToTGC(*lr_enu, 0.0)

    hole_dictionary = dict() # Holes must be ordered by hole_num.  Must keep track of return order just in case data doesn't have hole number
    for way in ways:
        golf_type = way.tags.get("golf", None)
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

            if golf_type == "green":
                course_json["surfaceSplines"].append(newGreen(nds))
            elif golf_type == "bunker":
                course_json["surfaceSplines"].append(newBunker(nds))
            elif golf_type == "tee":
                course_json["surfaceSplines"].append(newTeeBox(nds))
            elif golf_type == "fairway":
                course_json["surfaceSplines"].append(newFairway(nds))
            elif golf_type == "rough":
                course_json["surfaceSplines"].append(newRough(nds))
            elif golf_type == "water_hazard" or golf_type == "lateral_water_hazard":
                course_json["surfaceSplines"].append(newWaterHazard(nds))
            elif golf_type == "hole":
                par = int(way.tags.get("par", -1))
                hole_num = int(way.tags.get("ref", -1))
                hole = newHole(par, nds)
                if hole is not None:
                    if hole_num == 0:
                        hole_num = len(hole_dictionary) + 1
                    hole_dictionary[hole_num] = hole
            else:
                printf("Unsupported type: " + golf_type)

    # Insert all the found holes
    for key in sorted(hole_dictionary):
        course_json["holes"].append(hole_dictionary[key])

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
