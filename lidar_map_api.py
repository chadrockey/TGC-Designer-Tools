import cv2
import json
import math
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.widgets import RectangleSelector
import numpy as np
import sys
import time
import urllib

import OSMTGC
import tgc_tools
from usgs_lidar_parser import *

# Parameters
sample_scale = 2.0
desired_visible_points_per_pixel = 1.0
lidar_sample = 1 # Use every Nths lidar point.  1 is use all, 10 is use one of out 10
lidar_to_disk = False
status_print_duration = 1.0 # Print progress every n seconds

# 1 Unassigned
# 3 Low Vegetation
# 4 Medium Vegetation
# 5 High Vegetation
# 6 Building
# 7 Noise
# 9 Water

unwanted_classifications = [1, 3, 4, 5, 6, 7, 9]

# Global Variables for the UI
lower_x = 0
lower_y = 0
upper_x = 100
upper_y = 100

def image_median(im):
    return np.median(im[ im >= 0.0 ])

def line_select_callback(eclick, erelease):
    global lower_x
    global lower_y
    global upper_x
    global upper_y
    x1, y1 = eclick.xdata, eclick.ydata
    x2, y2 = erelease.xdata, erelease.ydata
    print("User Selection: (%3.2f, %3.2f) --> (%3.2f, %3.2f)" % (x1, y1, x2, y2))
    if x1 < x2:
        lower_x = math.floor(x1)
        upper_x = math.ceil(x2)
    else:
        lower_x = math.floor(x2)
        upper_x = math.ceil(x1)

    if y1 < y2:
        lower_y = math.floor(y1)
        upper_y = math.ceil(y2)
    else:
        lower_y = math.floor(y2)
        upper_y = math.ceil(y1)

def toggle_selector(event):
    print(' Key pressed.')
    if event.key in ['Q', 'q'] and toggle_selector.RS.active:
        print(' RectangleSelector deactivated.')
        toggle_selector.RS.set_active(False)
    if event.key in ['A', 'a'] and not toggle_selector.RS.active:
        print(' RectangleSelector activated.')
        toggle_selector.RS.set_active(True)

# Keep API out of code
with open("MAPQUEST_API_KEY.txt", "r") as f:
    API_KEY = f.read()

lidar_dir_path = None
keywords = []
if len(sys.argv) < 2:
    print("Usage: python program.py LAS_DIRECTORY")
    sys.exit(0)
elif len(sys.argv) == 2:
    lidar_dir_path = sys.argv[1]
else:
    lidar_dir_path = sys.argv[1]
    keywords = sys.argv[2:]

# Create directory for intermediate files
tgc_tools.create_export_directory(lidar_dir_path)

# Geocode request.  We'll need to use this to automatically try to find elevation data or to get the UTM zone for the las files
# Can't find a good source, so leave this out for now
'''with urllib.request.urlopen("http://open.mapquestapi.com/nominatim/v1/search.php?key=" + API_KEY + "&format=json&q=" + "+".join(keywords)) as url:
    print("http://open.mapquestapi.com/nominatim/v1/search.php?key=" + API_KEY + "&format=json&q=" + "+".join(keywords))
    geocode_data = json.loads(url.read().decode())
    print(geocode_data)'''

# Use provided las or get las files
pc = load_usgs_directory(lidar_dir_path)

image_width = math.ceil(pc.width/sample_scale)+1 # If image is exact multiple, then need one more pixel.  Example: 1500m -> 750 pixels, @1500, 750 isn't a valid pixel otherwise
image_height = math.ceil(pc.height/sample_scale)+1

print("Lidar image sampled size: " + str(image_width) + " x " + str(image_height))

print("Generating brightness and height images")
im = np.full((image_height,image_width,1), -1.0, np.float32)

img_points = pc.pointsAsCV2(sample_scale)
num_points = len(img_points)

point_density = float(num_points) / (image_width * image_height)

visible_sampling = math.floor(point_density/desired_visible_points_per_pixel) # Roughly get 1 sample per pixel for the visible image
if visible_sampling < 1.0:
    visible_sampling = 1

last_print_time = 0.0 + status_print_duration
for n, i in enumerate(img_points[0::visible_sampling]):
    if time.time() > last_print_time + status_print_duration:
        last_print_time = time.time()
        print(str(int(100.0*float(n*visible_sampling) / num_points)) + "% visualizing lidar")

    im[int(i[0]), int(i[1])] = i[3]

# Download OpenStreetMaps Data
print("Adding golf features to lidar data")

# Convert to RGB for pretty golf colors
im = np.clip(im, 0.0, 3.5*image_median(im))# Limit outlier pixels
im = im / np.max(im) # Normalize to 1.0
im  = cv2.cvtColor(im, cv2.COLOR_GRAY2RGB)

# Use this data to draw features on the intensity image to help with masking
upper_left_enu = pc.ulENU()
lower_right_enu = pc.lrENU()
upper_left_latlon = pc.enuToLatLon(*upper_left_enu)
lower_right_latlon = pc.enuToLatLon(*lower_right_enu)
# Order is South, West, North, East
result = OSMTGC.getOSMData(lower_right_latlon[0], upper_left_latlon[1], upper_left_latlon[0], lower_right_latlon[1])
im = OSMTGC.addOSMToImage(result.ways, im, pc, sample_scale)

#fig.title = "Draw the rectangle around the course on the left (in black and white)"
fig = plt.figure()
ax1 = fig.add_subplot(121)
ax1.title.set_text('Draw the rectangle around the course on the left (in black and white)\n \
                    Then close this window using the X.')
ax1.imshow(im, origin='lower')

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

img_url_request = "https://open.mapquestapi.com/staticmap/v5/map?key=" + API_KEY + "&scalebar=true&format=png&center=" + \
                        str(gps_center[0]) + "," + str(gps_center[1]) + \
                        "&type=hyb&zoom=" + str(zoom_level) + "&size=" + str(req_width) + "," + str(req_height)
print("Image URL Request: " + img_url_request)
try:
    # TODO switch to requests ?
    with urllib.request.urlopen(img_url_request) as url:
        map_image = url.read()

    nparr = np.frombuffer(map_image, np.uint8)
    im_map = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    ax2 = fig.add_subplot(122)
    ax2.title.set_text('Approximate Satellite View')
    ax2.imshow(cv2.cvtColor(im_map, cv2.COLOR_BGR2RGB))
except urllib.error.HTTPError as err:
    print("Could not get sat preview: " + str(err))

# drawtype is 'box' or 'line' or 'none'
toggle_selector.RS = RectangleSelector(ax1, line_select_callback,
                                       drawtype='box', useblit=True,
                                       button=[1, 3],  # don't use middle button
                                       minspanx=5, minspany=5,
                                       spancoords='pixels',
                                       interactive=True)

plt.show()

print("Generating heightmap")
om = np.full((image_height,image_width,1), -1.0, np.float32)
high_res_visual = np.full((image_height,image_width,1), -1.0, np.float32)

## Start cropping data and saving it for future steps
# Save only the relevant points from the raw pointcloud
llenu = pc.cv2ToENU(upper_y, lower_x, sample_scale)
urenu = pc.cv2ToENU(lower_y, upper_x, sample_scale)

# Remove the points not in the selection
# Use numpy to efficiently reduce the number of points we loop over to create the terrain image
selected_points = img_points[np.where(lower_y <= img_points[:,0])]
selected_points = selected_points[np.where(selected_points[:,0] < upper_y)]
selected_points = selected_points[np.where(lower_x <= selected_points[:,1])]
selected_points = selected_points[np.where(selected_points[:,1] < upper_x)]

# Remove points that aren't useful for ground heightmaps
selected_points = selected_points[np.isin(selected_points[:,4], unwanted_classifications, invert=True)]

# Generate heightmap only for the selected area
num_points = len(selected_points)
last_print_time = 0.0
for n, i in enumerate(selected_points[0::lidar_sample]):
    if time.time() > last_print_time + status_print_duration:
        last_print_time = time.time()
        print(str(int(100.0*float(n*lidar_sample) / num_points)) + "% generating heightmap")

    c = (int(i[0]), int(i[1]))

    # Add visual data
    value = high_res_visual[c]
    if value < 0:
        value = i[3]
    else:
        value = (i[3] - value) * 0.3 + value
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

output_points = []
if lidar_to_disk:
    print("Writing the original points to disk not yet supported")
    # TODO Apply same filters above to original pointcloud
    # Only need this if doing some kind of dynamic green resolution
    ''' for n, i in enumerate(pc.points()):
        if n % progress_interval == 0:
            print(str(int(100.0*float(n) / num_points)) + "% saving pointcloud")

        if i[4] in unwanted_classifications:
            continue # Filter out unwanted point classifications from elevation data

        if llenu[0] <= i[0] and i[0] <= urenu[0]:
            if llenu[1] <= i[1] and i[1] <= urenu[1]:
                    output_points.append(i)

    output_points = numpy.array(output_points)'''

fig = plt.figure()

ax1 = fig.add_subplot(121)
ax1.title.set_text('Cropped Brightness')

# Add OpenStreetMap to better quality visual
imc = np.copy(high_res_visual)
imc = np.clip(imc, 0.0, 3.5*image_median(imc)) # Limit outlier pixels
imc = imc / np.max(imc)
imc = cv2.cvtColor(imc, cv2.COLOR_GRAY2RGB)
imc = OSMTGC.addOSMToImage(result.ways, imc, pc, sample_scale)
imc = imc[lower_y:upper_y, lower_x:upper_x]
ax1.imshow(imc, origin='lower')
# Need to flip to write to disk in standard image order
imc = np.flip(imc, 0)
cv2.imwrite(lidar_dir_path + '/output/mask.png', cv2.cvtColor(255.0*imc, cv2.COLOR_RGB2BGR)) # not sure why it needs to be 255 scaled, but also needs a differnt colorspace

# Prepare nice looking copy of intensity image to save
high_res_visual = high_res_visual[lower_y:upper_y, lower_x:upper_x]
high_res_visual = np.clip(high_res_visual, 0.0, 3.5*image_median(high_res_visual)) # Limit outlier pixels
high_res_visual = high_res_visual / np.max(high_res_visual)
high_res_visual = cv2.cvtColor(high_res_visual, cv2.COLOR_GRAY2RGB)

ax2 = fig.add_subplot(122)
ax2.title.set_text('Elevation Map')
omc = om[lower_y:upper_y, lower_x:upper_x]
output_data = {'heightmap': omc}
output_data['visual'] = high_res_visual
output_data['pointcloud'] = output_points
output_data['image_scale'] = sample_scale
output_data['origin'] = pc.cv2ToLatLon(lower_y, lower_x, sample_scale) # Origin is lower left corner
output_data['projection'] = pc.proj
np.save(lidar_dir_path + '/output/heightmap', output_data) # Save as numpy format since we have raw float elevations

# Now that the height map is saved, make it look good for users
omd = np.clip(omc, 0.0, 3.5*np.mean(omc)) # Limit outlier pixels
omd = omd / np.max(omd) # Normalize to 0.0 to 1.0
ax2.imshow(cv2.cvtColor(omd, cv2.COLOR_GRAY2RGB)[:,:,0], cmap=plt.get_cmap('viridis'), origin='lower') # Draw heightmap, make clear colors

plt.show()
