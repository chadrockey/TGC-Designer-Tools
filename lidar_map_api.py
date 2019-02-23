import tkinter as tk
from tkinter import filedialog
from tkinter import *
import tkinter.ttk as ttk
from tkinter.scrolledtext import ScrolledText
import PIL
from PIL import Image, ImageTk

import cv2
from functools import partial
import json
import math
import numpy as np
import os
import scipy
import sys
import time
import urllib

import OSMTGC
import tgc_tools
import tree_mapper
from usgs_lidar_parser import *

# Parameters
desired_visible_points_per_pixel = 1.0
lidar_sample = 1 # Use every Nths lidar point.  1 is use all, 10 is use one of out 10
lidar_to_disk = False
status_print_duration = 1.0 # Print progress every n seconds

# 1 Unassigned
# 2 Ground
# 3 Low Vegetation
# 4 Medium Vegetation
# 5 High Vegetation
# 6 Building
# 7 Noise
# 8 Model Key Points
# 9 Water

wanted_classifications = [2, 8] # These are considered "bare earth"

# Global Variables for the UI
rect = None
rectid = None
rectx0 = 0
recty0 = 0
rectx1 = 10
recty1 = 10

lower_x = 0
lower_y = 0
upper_x = 10
upper_y = 10

running_as_main = False
canvas = None
im_img = None
sat_canvas = None
sat_img = None

move = False

def image_median(im):
    return np.median(im[ im >= 0.0 ])

def createCanvasBinding():
    global canvas
    global move
    global rect
    global rectid
    global rectx0
    global rectx1
    global recty0
    global recty1
    canvas.bind( "<Button-1>", startRect )
    canvas.bind( "<ButtonRelease-1>", stopRect )
    canvas.bind( "<Motion>", movingRect )

def startRect(event):
    global canvas
    global move
    global rect
    global rectid
    global rectx0
    global rectx1
    global recty0
    global recty1
    move = True
    rectx0 = canvas.canvasx(event.x)
    recty0 = canvas.canvasy(event.y) 
    if rect is not None:
        canvas.delete(rect)
    rect = canvas.create_rectangle(
        rectx0, recty0, rectx0, recty0, outline="#ff0000")
    rectid = canvas.find_closest(rectx0, recty0, halo=2)

def movingRect(event):
    global canvas
    global move
    global rectid
    global rectx0
    global rectx1
    global recty0
    global recty1
    if move: 
        rectx1 = canvas.canvasx(event.x)
        recty1 = canvas.canvasy(event.y)
        canvas.coords(rectid, rectx0, recty0,
                      rectx1, recty1)

def stopRect(event):
    global canvas
    global move
    global rectid
    global rectx0
    global rectx1
    global recty0
    global recty1
    move = False
    rectx1 = canvas.canvasx(event.x)
    recty1 = canvas.canvasy(event.y) 
    canvas.coords(rectid, rectx0, recty0,
                  rectx1, recty1)


def closeWindow(main, bundle, input_size, canvas_size, printf):
    global lower_x
    global lower_y
    global upper_x
    global upper_y
    main.destroy()

    # TODO im.thumbnail may return the actual image size and not the resized size, investigate  
    # Need to determine the preview size
    max_canvas_dimension = max([canvas_size[0], canvas_size[1]]) # Probably the same value
    width_over_height_ratio = float(input_size[0])/float(input_size[1])
    canvas_width = max_canvas_dimension * width_over_height_ratio
    canvas_height = max_canvas_dimension
    if width_over_height_ratio > 1.0: # Width is actually wider
        tmp = canvas_width
        canvas_width = max_canvas_dimension
        canvas_height = max_canvas_dimension / width_over_height_ratio

    width_ratio = float(input_size[0])/float(canvas_width)
    height_ratio = float(input_size[1])/float(canvas_height)

    lower_x = int(width_ratio*rectx0)
    upper_x = int(width_ratio*rectx1)
    if lower_x > upper_x:
        tmp = lower_x
        lower_x = upper_x
        upper_x = tmp

    lower_y = int(height_ratio*(canvas_size[1] - recty0))
    upper_y = int(height_ratio*(canvas_size[1] - recty1))
    if lower_y > upper_y:
        tmp = lower_y
        lower_y = upper_y
        upper_y = tmp

    generate_lidar_heightmap(*bundle, printf=printf)

def request_course_outline(course_image, sat_image=None, bundle=None, printf=print):
    global running_as_main
    global canvas
    global im_img
    global sat_canvas
    global sat_img

    input_size = (course_image.shape[1], course_image.shape[0]) # width, height
    preview_size = (600, 600) # Size of image previews

    # Create new window since this tool could be used as main
    if running_as_main:
        popup = tk.Tk()
    else:
        popup = tk.Toplevel()
    popup.geometry("1250x700")
    popup.wm_title("Select Course Boundaries")

    # Convert and resize for display
    im = Image.fromarray((255.0*course_image).astype(np.uint8), 'RGB')
    im = im.transpose(Image.FLIP_TOP_BOTTOM)
    im.thumbnail(preview_size, PIL.Image.LANCZOS) # Thumbnail is just resize but preserves aspect ratio
    cim = ImageTk.PhotoImage(image=im)

    instruction_frame = tk.Frame(popup)
    B1 = ttk.Button(instruction_frame, text="Accept", command = partial(closeWindow, popup, bundle, input_size, im.size, printf))
    label = ttk.Label(instruction_frame, text="Draw the rectangle around the course on the left (in black and white)\n \
                                   Then close this window using the Accept Button.", justify=CENTER)
    label.pack(fill="x", padx=10, pady=10)
    B1.pack()

    instruction_frame.pack()

    # Show both images
    image_frame = tk.Frame(popup)
    image_frame.pack()

    canvas = tk.Canvas(image_frame, width=preview_size[0], height=preview_size[1])
    im_img = canvas.create_image(0,0,image=cim,anchor=tk.NW)
    canvas.itemconfig(im_img, image=cim)
    canvas.image = im_img
    canvas.grid(row=0, column=0, sticky='w')

    if sat_image is not None:
        sim = Image.fromarray((sat_image).astype(np.uint8), 'RGB')
        sim.thumbnail(preview_size, PIL.Image.LANCZOS) # Thumbnail is just resize but preserves aspect ratio
        scim = ImageTk.PhotoImage(image=sim)
        sat_canvas = tk.Canvas(image_frame, width=preview_size[0], height=preview_size[1])
        sat_img = sat_canvas.create_image(0,0,image=scim,anchor=tk.NW)
        sat_canvas.itemconfig(sat_img, image=scim)
        sat_canvas.image = sat_img
        sat_canvas.grid(row=0, column=preview_size[0]+10, sticky='e')

    createCanvasBinding()

    popup.mainloop()


def generate_lidar_previews(lidar_dir_path, sample_scale, output_dir_path, force_epsg=None, force_unit=None, printf=print):
    # Create directory for intermediate files
    tgc_tools.create_directory(output_dir_path)

    # Use provided las or get las files
    pc = load_usgs_directory(lidar_dir_path, force_epsg=force_epsg, force_unit=force_unit, printf=printf)

    if pc is None:
        # Can't do anything with nothing
        return

    image_width = math.ceil(pc.width/sample_scale)+1 # If image is exact multiple, then need one more pixel.  Example: 1500m -> 750 pixels, @1500, 750 isn't a valid pixel otherwise
    image_height = math.ceil(pc.height/sample_scale)+1

    printf("Generating lidar intensity image")
    im = np.full((image_height,image_width,1), -1.0, np.float32)

    img_points = pc.pointsAsCV2(sample_scale)
    num_points = len(img_points)

    point_density = float(num_points) / (image_width * image_height)

    visible_sampling = math.floor(point_density/desired_visible_points_per_pixel) # Roughly get 1 sample per pixel for the visible image
    if visible_sampling < 1.0:
        visible_sampling = 1

    # Some pointclouds don't have intensity channel, so try to visualize elevation instead?
    visualization_axis = 3
    if pc.imin == pc.imax:
        printf("No lidar intensity found, using elevation instead")
        visualization_axis = 2
        # Remove everything but ground points to try to provide context to the visualized heightmap
        img_points = img_points[np.isin(img_points[:,4], wanted_classifications)]

    last_print_time = time.time()
    for n, i in enumerate(img_points[0::visible_sampling]):
        if time.time() > last_print_time + status_print_duration:
            last_print_time = time.time()
            printf(str(round(100.0*float(n*visible_sampling) / num_points, 2)) + "% visualizing lidar")
        im[int(i[0]), int(i[1])] = i[visualization_axis]

    # Download OpenStreetMaps Data
    printf("Adding golf features to lidar data")

    # Convert to RGB for pretty golf colors
    im = np.clip(im, 0.0, 3.5*image_median(im))# Limit outlier pixels
    im = (im - np.min(im)) / (np.max(im) - np.min(im)) # Normalize to 1.0
    im  = cv2.cvtColor(im, cv2.COLOR_GRAY2RGB)

    # Use this data to draw features on the intensity image to help with masking
    upper_left_enu = pc.ulENU()
    lower_right_enu = pc.lrENU()
    upper_left_latlon = pc.enuToLatLon(*upper_left_enu)
    lower_right_latlon = pc.enuToLatLon(*lower_right_enu)
    # Order is South, West, North, East
    result = OSMTGC.getOSMData(lower_right_latlon[0], upper_left_latlon[1], upper_left_latlon[0], lower_right_latlon[1], printf=printf)
    im = OSMTGC.addOSMToImage(result.ways, im, pc, sample_scale, printf=printf)

    # Keep API out of code
    mapquest_api_key = None
    im_map = None
    try:
        this_file_directory = os.path.dirname(os.path.realpath(__file__))
        with open(this_file_directory + os.sep + "MAPQUEST_API_KEY.txt", "r") as f:
            mapquest_api_key = f.read()
    except:
        pass
    if mapquest_api_key is not None:
        # Grab a preview image approximately the same to help reference the lidar data.
        # Set margin to be 1/8 of image size to get preview to about 1 pixel per two meters
        origin_projected_coordinates = pc.origin
        gps_center = pc.projToLatLon(origin_projected_coordinates[0] + pc.width / 2.0, origin_projected_coordinates[1] + pc.height / 2.0)

        # Determine how zoomed in the map should be
        zoom_level = 20 # Most zoomed in possible
        max_dimension = max([image_width, image_height])
        if sample_scale*max_dimension < 500:
            zoom_level = 19 # roughly 437m
        elif sample_scale*max_dimension < 900:
            zoom_level = 18 # roughly 875m
        elif sample_scale*max_dimension < 1800:
            zoom_level = 17 # roughly 1750m
        elif sample_scale*max_dimension < 3600:
            zoom_level = 16 # roughly 3500m
        elif sample_scale*max_dimension < 7000:
            zoom_level = 15 # roughly 7000m
        else:
            zoom_level = 14 # Over 7000m

        # Determine the aspect ratio
        req_height = 1500
        req_width = 1500
        if max_dimension == image_width: # Shrink height
            req_height = int(1500.0*float(image_height)/float(image_width))
        else: # Shrink width
            req_width = int(1500.0*float(image_width)/float(image_height))

        img_url_request = "https://open.mapquestapi.com/staticmap/v5/map?key=MAPQUEST_API_KEY&scalebar=true&format=png&center=" + \
                                str(gps_center[0]) + "," + str(gps_center[1]) + \
                                "&type=hyb&zoom=" + str(zoom_level) + "&size=" + str(req_width) + "," + str(req_height)

        printf("Mapquest Image URL Request: " + img_url_request)

        # Don't print the Mapquest API Key to users
        img_url_request = img_url_request.replace("MAPQUEST_API_KEY", mapquest_api_key)

        try:
            # TODO switch to requests ?
            with urllib.request.urlopen(img_url_request) as url:
                map_image = url.read()

            nparr = np.frombuffer(map_image, np.uint8)
            im_map = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            im_map = cv2.cvtColor(im_map, cv2.COLOR_BGR2RGB)
        except urllib.error.HTTPError as err:
            printf("Could not get sat preview: " + str(err))

    request_course_outline(im, im_map, bundle=(pc, img_points, sample_scale, output_dir_path, result), printf=printf)

def generate_lidar_heightmap(pc, img_points, sample_scale, output_dir_path, osm_results=None, printf=print):
    global lower_x
    global lower_y
    global upper_x
    global upper_y
    image_width = math.ceil(pc.width/sample_scale)+1 # If image is exact multiple, then need one more pixel.  Example: 1500m -> 750 pixels, @1500, 750 isn't a valid pixel otherwise
    image_height = math.ceil(pc.height/sample_scale)+1

    printf("Generating heightmap")
    om = np.full((image_height,image_width,1), -1.0, np.float32)
    high_res_visual = np.full((image_height,image_width,1), -1.0, np.float32)

    # Make sure selected limits are in bounds, otherwise limit them
    # This can happen if the rectangle goes outside the image
    lower_x = max(0, lower_x)
    lower_y = max(0, lower_y)
    upper_x = min(image_width, upper_x)
    upper_y = min(image_height, upper_y)

    ## Start cropping data and saving it for future steps
    # Save only the relevant points from the raw pointcloud
    printf("Selecting only needed data from lidar")
    llenu = pc.cv2ToENU(upper_y, lower_x, sample_scale)
    urenu = pc.cv2ToENU(lower_y, upper_x, sample_scale)

    # Remove the points not in the selection
    # Use numpy to efficiently reduce the number of points we loop over to create the terrain image
    selected_points = img_points[np.where(lower_y <= img_points[:,0])]
    selected_points = selected_points[np.where(selected_points[:,0] < upper_y)]
    selected_points = selected_points[np.where(lower_x <= selected_points[:,1])]
    selected_points = selected_points[np.where(selected_points[:,1] < upper_x)]

    # Remove points that aren't useful for ground heightmaps
    ground_points = numpy.copy(selected_points) # Copy to preserve selected points for other uses like tree detection
    ground_points = ground_points[np.isin(ground_points[:,4], wanted_classifications)]

    if len(ground_points) == 0:
        printf("\n\n\nSorry, this lidar data is not classified and I can't support it right now.  Ask for help on the forum or your lidar provider if they have a classified version.")
        printf("Classification is where they determine which points are the ground and which are trees, buildings, etc.  I can't make a nice looking course without clean input.")
        return

    # Some pointclouds don't have intensity channel, so try to visualize elevation instead?
    visualization_axis = 3
    if pc.imin == pc.imax:
        printf("No lidar intensity found, using elevation instead")
        visualization_axis = 2

    # Generate heightmap only for the selected area
    num_points = len(ground_points)
    last_print_time = time.time()
    for n, i in enumerate(ground_points[0::lidar_sample]):
        if time.time() > last_print_time + status_print_duration:
            last_print_time = time.time()
            printf(str(round(100.0*float(n*lidar_sample) / num_points, 2)) + "% generating heightmap")

        c = (int(i[0]), int(i[1]))

        # Add visual data
        value = high_res_visual[c]
        if value < 0:
            value = i[visualization_axis]
        else:
            value = (i[visualization_axis] - value) * 0.3 + value
        high_res_visual[c] = value

        # Add elevation data
        elevation = om[c]
        if elevation < 0: # Todo can this if be removed?
            elevation = i[2]
        else:
            alpha = 0.1
            if i[2] < elevation:
                # Trend lower faster
                alpha = 0.4
            elevation = (i[2] - elevation) * alpha + elevation
        om[c] = elevation

    printf("Finished generating heightmap")

    printf("Starting tree detection")
    trees = []
    # Make a maximum heightmap
    # Must be around 1 meter grid size and a power of 2 from sample_scale
    tree_ratio = 2**(math.ceil(math.log2(1.0/sample_scale)))
    tree_scale = sample_scale * tree_ratio
    printf("Tree ratio is: " + str(tree_ratio))
    treemap = np.full((int(image_height/tree_ratio),int(image_width/tree_ratio),1), -1.0, np.float32)
    num_points = len(selected_points)
    last_print_time = time.time()
    for n, i in enumerate(selected_points[0::lidar_sample]):
        if time.time() > last_print_time + status_print_duration:
            last_print_time = time.time()
            printf(str(round(100.0*float(n*lidar_sample) / num_points, 2)) + "% generating object map")

        c = (int(i[0]/tree_ratio), int(i[1]/tree_ratio))

        # Add elevation data
        if i[2] > treemap[c]:
            # Just take the maximum value possible for this pixel
            treemap[c] = i[2]
    # Make a resized copy of the ground height that matches the object detection image size
    groundmap = np.copy(om[lower_y:upper_y, lower_x:upper_x])
    groundmap = numpy.array(Image.fromarray(groundmap[:,:,0], mode='F').resize((int(groundmap.shape[1]/tree_ratio), int(groundmap.shape[0]/tree_ratio)), resample=Image.NEAREST))
    groundmap = np.expand_dims(groundmap, axis=2) # Workaround until the extra image dimension is removed
    img_trees = tree_mapper.getTreeCoordinates(groundmap, treemap[int(lower_y/tree_ratio):int(upper_y/tree_ratio), int(lower_x/tree_ratio):int(upper_x/tree_ratio)], printf=printf)
    trees = []
    for t in img_trees:
        # Convert to projection for better portability
        proj = pc.cv2ToProj(int(lower_y/tree_ratio)+t[1], int(lower_x/tree_ratio)+t[0], tree_scale)
        trees.append((proj[0], proj[1], t[2], t[3]))

    printf("Writing files to disk")
    output_points = []
    if lidar_to_disk:
        printf("Writing the original points to disk not yet supported")
        # TODO Apply same filters above to original pointcloud
        # Only need this if doing some kind of dynamic green resolution
        ''' for n, i in enumerate(pc.points()):
            if n % progress_interval == 0:
                printf(str(int(100.0*float(n) / num_points)) + "% saving pointcloud")

            if i[4] in unwanted_classifications:
                continue # Filter out unwanted point classifications from elevation data

            if llenu[0] <= i[0] and i[0] <= urenu[0]:
                if llenu[1] <= i[1] and i[1] <= urenu[1]:
                        output_points.append(i)

        output_points = numpy.array(output_points)'''

    # Add OpenStreetMap to better quality visual
    imc = np.copy(high_res_visual)
    imc = np.clip(imc, 0.0, 3.5*image_median(imc)) # Limit outlier pixels
    imc = (imc - np.min(imc)) / (np.max(imc) - np.min(imc))
    imc = cv2.cvtColor(imc, cv2.COLOR_GRAY2RGB)
    if osm_results:
        imc = OSMTGC.addOSMToImage(osm_results.ways, imc, pc, sample_scale)
    imc = imc[lower_y:upper_y, lower_x:upper_x]
    # Need to flip to write to disk in standard image order
    imc = np.flip(imc, 0)
    printf("Saving mask as: " + str(output_dir_path) + '/mask.png')
    cv2.imwrite(output_dir_path + '/mask.png', cv2.cvtColor(255.0*imc, cv2.COLOR_RGB2BGR)) # not sure why it needs to be 255 scaled, but also needs a differnt colorspace

    # Prepare nice looking copy of intensity image to save
    high_res_visual = high_res_visual[lower_y:upper_y, lower_x:upper_x]
    high_res_visual = np.clip(high_res_visual, 0.0, 3.5*image_median(high_res_visual)) # Limit outlier pixels
    high_res_visual = (high_res_visual - np.min(high_res_visual)) / (np.max(high_res_visual) - np.min(high_res_visual))
    high_res_visual = cv2.cvtColor(high_res_visual, cv2.COLOR_GRAY2RGB)

    omc = om[lower_y:upper_y, lower_x:upper_x]
    output_data = {'heightmap': omc}
    output_data['visual'] = high_res_visual
    output_data['pointcloud'] = output_points
    output_data['image_scale'] = sample_scale
    output_data['origin'] = pc.cv2ToLatLon(lower_y, lower_x, sample_scale) # Origin is lower left corner
    output_data['projection'] = pc.proj
    output_data['trees'] = trees
    printf("Saving data as: " + str(output_dir_path) + '/heightmap.npy')
    np.save(output_dir_path + '/heightmap', output_data) # Save as numpy format since we have raw float elevations

    printf("Done!  Now go edit your mask.png to remove uneeded areas")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python program.py LAS_DIRECTORY OUTPUT_DIRECTORY METERS_PER_PIXEL [FORCE_EPSG] [FORCE_UNIT]")
        sys.exit(0)
    else:
        lidar_dir_path = sys.argv[1]
        output_dir = sys.argv[2]
        meters_per_pixel = float(sys.argv[3])
        try:
            force_epsg = int(sys.argv[4])
        except:
            force_epsg = None
        try:
            force_unit = float(sys.argv[5])
        except:
            force_unit = None

    running_as_main = True
    generate_lidar_previews(lidar_dir_path, meters_per_pixel, output_dir, force_epsg=force_epsg, force_unit=force_unit)
