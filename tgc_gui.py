import tkinter as tk
from tkinter import filedialog
from tkinter import *
import tkinter.ttk as ttk
from tkinter.scrolledtext import ScrolledText

import copy
import cv2
from functools import partial
import math
import numpy as np
import numpy
from PIL import Image, ImageTk

import tgc_tools
import lidar_map_api
import tgc_image_terrain
from tgc_visualizer import drawCourseAsImage

TGC_GUI_VERSION = "0.0.1"

image_width = 500
image_height = 500

# Make placeholder image
data=numpy.array(numpy.random.random((image_width,image_height))*100,dtype=int)
iim=Image.frombytes('L', (data.shape[1],data.shape[0]), data.astype('b').tostring())

root = None
canvas = None
canvas_image = None
course_json = None

def drawPlaceholder():
    global root
    global canvas
    global canvas_image
    default_im = ImageTk.PhotoImage(image=iim)
    canvas.itemconfig(canvas_image, image = default_im)
    root.update()

def drawCourse(cjson):
    global root
    global canvas
    global canvas_image
    data = drawCourseAsImage(cjson)
    im = Image.fromarray((255.0*data).astype(np.uint8), 'RGB').resize((image_width, image_height), Image.NEAREST)
    im = im.transpose(Image.FLIP_TOP_BOTTOM)
    cim = ImageTk.PhotoImage(image=im)

    canvas.img = cim # Need to save reference to ImageTK
    canvas.itemconfig(canvas_image, image = cim)
    root.update()

def getCourseDirectory(output):
    global root
    global course_json
    cdir =  tk.filedialog.askdirectory(initialdir = ".", title = "Select course directory")
    if cdir:
        root.filename = cdir
        output.config(text=root.filename)

        drawPlaceholder() # Clear out existing course while picking a new one

        try:
            course_json = tgc_tools.get_course_json(root.filename)
            if course_json is not None:
                drawCourse(course_json)
        except:
            pass

def alert(msg):
    popup = tk.Toplevel()
    popup.geometry("200x200")
    popup.wm_title("Alert")
    label = ttk.Label(popup, text=msg, wraplength=200, justify=CENTER)
    label.pack(side="top", fill="x", pady=10)
    B1 = ttk.Button(popup, text="OK", command = popup.destroy)
    B1.pack()
    popup.mainloop()

def disableAllChildren(var, frame):
    for child in frame.winfo_children():
        if var.get(): # Check enabled
            child['state'] = 'normal'
        else:
            child['state'] = 'disable'

course_types = [
    ('Golf Course Files', '*.course'), 
    ('All files', '*'), 
]

def importCourseAction():
    global root
    global course_json

    if not root or not hasattr(root, 'filename'):
        alert("Select a course directory before importing a .course file")
        return

    input_course = tk.filedialog.askopenfilename(title='Course File', defaultextension='course', initialdir=root.filename, filetypes=course_types)

    if input_course:
        drawPlaceholder()
        tgc_tools.unpack_course_file(root.filename, input_course)
        course_json = tgc_tools.get_course_json(root.filename)
        drawCourse(course_json)

def exportCourseAction():
    global root
    global course_json

    if not root or not hasattr(root, 'filename'):
        alert("Select a course directory before exporting a .course file")
        return

    dest_file = tk.filedialog.asksaveasfilename(title='Save Course As', defaultextension='.course', initialdir=root.filename, confirmoverwrite=True, filetypes=course_types)

    if dest_file:
        tgc_tools.pack_course_file(root.filename, None, dest_file, course_json)

def autoPositionAction():
    global course_json
    drawPlaceholder()
    course_json = tgc_tools.auto_position_course(course_json)
    drawCourse(course_json)

def shiftAction(ew_entry, ns_entry, stype="course"):
    global course_json
    try:
        easting_shift = float(ew_entry.get())
        northing_shift = float(ns_entry.get())
    except:
        print("No action taken: Could not get valid shifts from entry")
        return
    drawPlaceholder()
    if stype == "course":
        course_json = tgc_tools.shift_course(course_json, easting_shift, northing_shift)
    elif stype == "terrain":
        course_json = tgc_tools.shift_terrain(course_json, easting_shift, northing_shift)
    elif stype == "features":
        course_json = tgc_tools.shift_features(course_json, easting_shift, northing_shift)
    else:
        print("No action taken: Unknown shift type: " + stype)
    drawCourse(course_json)

def rotateAction(rotate_entry):
    global course_json
    try:
        rotation_degrees = float(rotate_entry.get())
        rotation = rotation_degrees * math.pi / 180.0
    except:
        print("No action taken: Could not get valid rotation from entry")
        return

    drawPlaceholder()
    course_json = tgc_tools.rotate_course(course_json, -rotation)
    drawCourse(course_json)

def elevateAction(elevate_entry, auto=False):
    global course_json
    elevation_shift = None
    if not auto:
        try:
            elevation_shift = float(elevate_entry.get())
        except:
            print("No action taken: Could not get valid elevation shift from entry")
            return

    if elevation_shift is not None and elevation_shift == 0.0:
        # Need to not pass in 0.0 or auto elevation shift will be triggered
        print("No action taken: shift requested was zero")
        return

    drawPlaceholder()
    course_json = tgc_tools.elevate_terrain(course_json, elevation_shift)
    drawCourse(course_json)

numpy_types = [
    ('Golf Course Features', '*.npy'), 
    ('All files', '*'), 
]

def separateAction(stype="terrain"):
    global course_json
    if stype == "terrain":
        name = "Terrain"
        f = tgc_tools.strip_terrain
    else:
        print("No action taken: Unknown separate type: " + stype)

    dest_file = tk.filedialog.asksaveasfilename(title=name+' filename', defaultextension='.npy', initialdir=root.filename, confirmoverwrite=True, filetypes=numpy_types)

    if dest_file:
        drawPlaceholder()
        course_json = f(course_json, dest_file)
        drawCourse(course_json)

def insertAction(stype="terrain"):
    global course_json
    if stype == "terrain":
        name = "Terrain"
        f = tgc_tools.insert_terrain
    else:
        print("No action taken: Unknown insert type: " + stype)

    input_file = tk.filedialog.askopenfilename(title=name+' filename', defaultextension='npy', initialdir=root.filename, filetypes=numpy_types)

    if input_file:
        drawPlaceholder()
        course_json = f(course_json, input_file)
        drawCourse(course_json)

def confirmCourse(popup, new_course_json):
    global course_json

    popup.destroy()

    drawPlaceholder()
    if  new_course_json is not None:
        course_json = new_course_json
    drawCourse(course_json)

def combineAction():
    global course_json
    other_course_dir = tk.filedialog.askdirectory(initialdir = ".", title = "Select second course directory")

    if other_course_dir:
        drawPlaceholder()
        course1_json = copy.deepcopy(course_json) # Make copy so this isn't "permanent" in memory
        course2_json = tgc_tools.get_course_json(other_course_dir)

        course1_json = tgc_tools.merge_courses(course1_json, course2_json)
        drawCourse(course1_json)

        popup = tk.Toplevel()
        popup.geometry("400x400")
        popup.wm_title("Confirm course merge?")
        label = ttk.Label(popup, text="Confirm course merge?")
        label.pack(side="top", fill="x", pady=10)
        B1 = ttk.Button(popup, text="Yes, Merge", command = partial(confirmCourse, popup, course1_json))
        B1.pack()
        B2 = ttk.Button(popup, text="No, Abandon Merge", command = partial(confirmCourse, popup, None))
        B2.pack()
        popup.mainloop()

def tkinterPrintFunction(root, textfield, message):
    textfield.configure(state='normal')
    textfield.insert(tk.END, message + "\n")
    textfield.configure(state='disabled')
    textfield.see(tk.END)
    root.update()

def runLidar(scale_entry, epsg_entry, unit_entry, printf):
    global root

    if not root or not hasattr(root, 'filename'):
        alert("Select a course directory before processing lidar files")
        return

    try:
        sample_scale = float(scale_entry.get())
    except:
        alert("No action taken: Could not get valid resolution from entry")
        return

    force_epsg = None
    try:
        epsg_raw = epsg_entry.get()
        if epsg_raw: # Don't process empty string
            force_epsg = int(epsg_raw)
    except:
        alert("No action taken: Could not get valid force epsg from entry")
        return

    force_unit = None
    try:
        unit_raw = unit_entry.get()
        if unit_raw: # Don't process empty string
            force_unit = float(unit_raw)
    except:
        alert("No action taken: Could not get valid force unit from entry")
        return

    lidar_dir_path = tk.filedialog.askdirectory(initialdir=root.filename, title="Select las/laz files directory")
    if lidar_dir_path:
        lidar_map_api.generate_lidar_previews(lidar_dir_path, sample_scale, root.filename, force_epsg=force_epsg, force_unit=force_unit, printf=printf)

def generateCourseFromLidar(options_entries_dict, printf):
    global root
    global course_json

    if not root or not hasattr(root, 'filename'):
        alert("Select a course directory before processing heightmap file")
        return

    # There may be many options for this in the future (which splines to add, clear splines?, flatten fairways/greens, etc) so store efficiently
    options_dict = {}

    # Snapshot the current values of the entries dictionary into the options_dict
    # We are reusing the same keys, so try not to change them often
    # All values in the entries_dict must support the get() function
    for key, entry in options_entries_dict.items():
        options_dict[key] = entry.get()

    heightmap_dir_path = tk.filedialog.askdirectory(initialdir=root.filename, title="Select heightmap and mask files directory")
    if heightmap_dir_path:
        drawPlaceholder()
        course_json = tgc_image_terrain.generate_course(course_json, heightmap_dir_path, options_dict=options_dict, printf=printf)
        drawCourse(course_json)
        printf("Done Rendering Course Preview")

root = tk.Tk()
root.geometry("800x600")

style = ttk.Style()
style.theme_create( "TabStyle", parent="alt", settings={
        "TNotebook": {"configure": {"tabmargins": [2, 5, 2, 0] } },
        "TNotebook.Tab": {"configure": {"padding": [30, 5] },}})

style.theme_use("TabStyle")

root.title("TGC Golf Tools " + TGC_GUI_VERSION)

header_frame = Frame(root)
output = Label(header_frame, background="lightgrey", width=75, height=1)
output.pack(side=LEFT)
B = Button(header_frame, text = "Select Course Directory", command = partial(getCourseDirectory, output))
B.pack(side=LEFT)
header_frame.pack(fill=X)

nb = ttk.Notebook(root)

s = ttk.Style()
s.configure('new.TFrame', background='#A9A9A9')

tools = ttk.Frame(nb, style='new.TFrame')
lidar = ttk.Frame(nb, style='new.TFrame')
course = ttk.Frame(nb, style='new.TFrame')
nb.pack(fill=BOTH, expand=1)
nb.add(tools, text='Course Tools')
nb.add(lidar, text='Process Lidar')
nb.add(course, text='Import Terrain and Features')

## Tools Tab
image_frame = Frame(tools, width=image_width, height=image_height)
image_frame.pack(anchor=NW, side=LEFT)
canvas = tk.Canvas(image_frame, width=image_width, height=image_height)
canvas.place(x=0,y=0)

bg_color = "darkgrey"
tool_bg = "grey25"
text_fg = "grey90"

tool_buttons_frame = Frame(tools, bg=bg_color)
tool_buttons_frame.pack(side=LEFT, fill=BOTH, expand=1)

ib = Button(tool_buttons_frame, text="Import .course", command=importCourseAction)
ib.pack(pady=5)
eb = Button(tool_buttons_frame, text="Export .course", command=exportCourseAction)
eb.pack(pady=5)
apb = Button(tool_buttons_frame, text="Auto Position", command=autoPositionAction)
apb.pack(pady=5)

# Buttons that move things
move_frame = Frame(tool_buttons_frame, bg=tool_bg)
Label(move_frame, text="West->East", fg=text_fg, bg=tool_bg).grid(row=0, sticky=W, padx=5)
Label(move_frame, text="South->North", fg=text_fg, bg=tool_bg).grid(row=1, sticky=W, padx=5)
ew = tk.Entry(move_frame, width=10, justify='center')
ew.insert(END, '0.0')
ew.grid(row=0, column=1, padx=5)
ns = tk.Entry(move_frame, width=10, justify='center')
ns.insert(END, '0.0')
ns.grid(row=1, column=1, padx=5)
move_buttons_frame = Frame(move_frame, bg=tool_bg)
mcb = Button(move_buttons_frame, text="Move Course", command=partial(shiftAction, ew, ns, "course"))
mcb.pack(pady=5)
mtb = Button(move_buttons_frame, text="Shift Terrain", command=partial(shiftAction, ew, ns, "terrain"))
mtb.pack(pady=5)
mfb = Button(move_buttons_frame, text="Shift Features", command=partial(shiftAction, ew, ns, "features"))
mfb.pack(pady=5)
move_buttons_frame.grid(row=0, column=2, rowspan=2, padx=10)
move_frame.pack(pady=5)

# Rotation with text field
rotate_frame = Frame(tool_buttons_frame, bg=tool_bg)
Label(rotate_frame, text="Rotation (Degrees)", fg=text_fg, bg=tool_bg).grid(row=0, sticky=W, padx=5)
er = tk.Entry(rotate_frame, width=8, justify='center')
er.insert(END, '0.0')
er.grid(row=0, column=1, padx=5)
rb = Button(rotate_frame, text="Rotate", command=partial(rotateAction, er))
rb.grid(row=0, column=2, padx=10, pady=5)
rotate_frame.pack(pady=5)

# Elevation shift
aeb = Button(tool_buttons_frame, text="Auto Shift Elevations", command=partial(elevateAction, None, True))
aeb.pack(pady=5)

elevate_frame = Frame(tool_buttons_frame, bg=tool_bg)
Label(elevate_frame, text="Down->Up", fg=text_fg, bg=tool_bg).grid(row=0, sticky=W, padx=5)
ee = tk.Entry(elevate_frame, width=8, justify='center')
ee.insert(END, '0.0')
ee.grid(row=0, column=1, padx=5)
etb = Button(elevate_frame, text="Shift Elevations", command=partial(elevateAction, ee))
etb.grid(row=0, column=2, padx=10, pady=5)
elevate_frame.pack(pady=5)

stb = Button(tool_buttons_frame, text="Separate Terrain", command=partial(separateAction, "terrain"))
stb.pack(pady=5)
itb = Button(tool_buttons_frame, text="Insert Terrain File", command=partial(insertAction, "terrain"))
itb.pack(pady=5)
ccb = Button(tool_buttons_frame, text="Combine Course Directory", command=combineAction)
ccb.pack(pady=5)

default_im = ImageTk.PhotoImage(image=iim)
canvas_image = canvas.create_image(0,0,image=default_im,anchor=tk.NW)
root.update()

## Lidar Tab
lidarConsoleOutput = tk.scrolledtext.ScrolledText(master=lidar, wrap=tk.WORD, width=20, height=10, state=DISABLED)
lidarPrintf = partial(tkinterPrintFunction, lidar, lidarConsoleOutput)

lidarControlFrame = Frame(lidar, bg=tool_bg)

scale_label = Label(lidarControlFrame, text="Map Resolution", fg=text_fg, bg=tool_bg)
scale_entry = tk.Entry(lidarControlFrame, width=8, justify='center')
scale_entry.insert(END, 2.0)
epsg_label = Label(lidarControlFrame, text="Force Lidar EPSG Projection", fg=text_fg, bg=tool_bg)
epsg_entry = tk.Entry(lidarControlFrame, width=8, justify='center')
epsg_entry.insert(END, "")
lidar_unit_label = Label(lidarControlFrame, text="Force Lidar Unit", fg=text_fg, bg=tool_bg)
lidar_unit_entry = tk.Entry(lidarControlFrame, width=8, justify='center')
lidar_unit_entry.insert(END, "")
lidarbutton = Button(lidarControlFrame, text="Select Lidar and Generate Heightmap", command=partial(runLidar, scale_entry, epsg_entry, lidar_unit_entry, lidarPrintf))

scale_label.pack(side=LEFT, padx=5)
scale_entry.pack(side=LEFT, padx=5)
epsg_label.pack(side=LEFT, padx=5)
epsg_entry.pack(side=LEFT, padx=5)
lidar_unit_label.pack(side=LEFT, padx=5)
lidar_unit_entry.pack(side=LEFT, padx=5)
lidarbutton.pack(side=LEFT, padx=5, pady=5)

lidarControlFrame.pack(pady=5)
lidarConsoleOutput.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

## Import Terrain and Features Tab
courseConsoleOutput = tk.scrolledtext.ScrolledText(master=course, wrap=tk.WORD, width=20, height=10, state=DISABLED)
coursePrintf = partial(tkinterPrintFunction, course, courseConsoleOutput)

courseControlFrame = Frame(course, bg=bg_color)

options_entries_dict = {} # Store the many entries into one dictionary

# OpenStreetMap Options
check_fg = "black" # Check fg can't be light or near white or it is invisible in the checkbox
check_bg = "grey80"
osmControlFrame = Frame(courseControlFrame, bg=tool_bg)
osmSubFrame = Frame(osmControlFrame, bg=check_bg) # Can disable all OSM Options easily inside of this

options_entries_dict["use_osm"] = tk.BooleanVar()
useOSMCheck = Checkbutton(osmControlFrame, text="Import OpenStreetMap", variable=options_entries_dict["use_osm"], fg=check_fg, bg="grey60")
useOSMCheck['command'] = partial(disableAllChildren, options_entries_dict["use_osm"], osmSubFrame)
useOSMCheck.select() # Default to Checked

Label(osmSubFrame, text="Fine Shift West->East", fg=check_fg, bg=check_bg).grid(row=0, sticky=W, padx=5)
Label(osmSubFrame, text="Fine Shift South->North", fg=check_fg, bg=check_bg).grid(row=1, sticky=W, padx=5)
osmew = tk.Entry(osmSubFrame, width=10, justify='center')
osmew.insert(END, '0.0')
options_entries_dict["adjust_ew"] = osmew
osmns = tk.Entry(osmSubFrame, width=10, justify='center')
osmns.insert(END, '0.0')
options_entries_dict["adjust_ns"] = osmns

options_entries_dict["bunker"] = tk.BooleanVar()
bunkerCheck = Checkbutton(osmSubFrame, text="Import Bunkers", variable=options_entries_dict["bunker"], fg=check_fg, bg=check_bg)
bunkerCheck.select()
options_entries_dict["green"] = tk.BooleanVar()
greenCheck = Checkbutton(osmSubFrame, text="Import Greens", variable=options_entries_dict["green"], fg=check_fg, bg=check_bg)
greenCheck.select()
options_entries_dict["fairway"] = tk.BooleanVar()
fairwayCheck = Checkbutton(osmSubFrame, text="Import Fairways", variable=options_entries_dict["fairway"], fg=check_fg, bg=check_bg)
fairwayCheck.select()
options_entries_dict["range"] = tk.BooleanVar()
rangeCheck = Checkbutton(osmSubFrame, text="Import Driving Ranges", variable=options_entries_dict["range"], fg=check_fg, bg=check_bg)
rangeCheck.select()
options_entries_dict["teebox"] = tk.BooleanVar()
teeboxCheck = Checkbutton(osmSubFrame, text="Import Teeboxes", variable=options_entries_dict["teebox"], fg=check_fg, bg=check_bg)
teeboxCheck.select()
options_entries_dict["rough"] = tk.BooleanVar()
roughCheck = Checkbutton(osmSubFrame, text="Import Rough", variable=options_entries_dict["rough"], fg=check_fg, bg=check_bg)
roughCheck.select()
options_entries_dict["water"] = tk.BooleanVar()
waterCheck = Checkbutton(osmSubFrame, text="Import Water Hazards", variable=options_entries_dict["water"], fg=check_fg, bg=check_bg)
waterCheck.select()
options_entries_dict["cartpath"] = tk.BooleanVar()
cartpathCheck = Checkbutton(osmSubFrame, text="Import Cartpaths", variable=options_entries_dict["cartpath"], fg=check_fg, bg=check_bg)
cartpathCheck.select()
options_entries_dict["path"] = tk.BooleanVar()
pathCheck = Checkbutton(osmSubFrame, text="Import Walking Paths", variable=options_entries_dict["path"], fg=check_fg, bg=check_bg)
pathCheck.select()
options_entries_dict["hole"] = tk.BooleanVar()
holeCheck = Checkbutton(osmSubFrame, text="Import Holes", variable=options_entries_dict["hole"], fg=check_fg, bg=check_bg)
holeCheck.select()

osmew.grid(row=0, column=1, padx=5)
osmns.grid(row=1, column=1, padx=5)
bunkerCheck.grid(row=2, columnspan=2, sticky=W, padx=5)
greenCheck.grid(row=3, columnspan=2, sticky=W, padx=5)
fairwayCheck.grid(row=4, columnspan=2, sticky=W, padx=5)
rangeCheck.grid(row=5, columnspan=2, sticky=W, padx=5)
teeboxCheck.grid(row=6, columnspan=2, sticky=W, padx=5)
roughCheck.grid(row=7, columnspan=2, sticky=W, padx=5)
waterCheck.grid(row=8, columnspan=2, sticky=W, padx=5)
cartpathCheck.grid(row=9, columnspan=2, sticky=W, padx=5)
pathCheck.grid(row=10, columnspan=2, sticky=W, padx=5)
holeCheck.grid(row=11, columnspan=2, sticky=W, padx=5)

useOSMCheck.pack(padx=10, pady=10)
osmSubFrame.pack(padx=5, pady=5)

coursebutton = Button(courseControlFrame, text="Select and Import Heightmap and OSM into Course", command=partial(generateCourseFromLidar, options_entries_dict, coursePrintf))

# Pack the controls frames, button at the top followed by the options
coursebutton.pack(padx=10, pady=10)

# Other Course Options
courseOptionsFrame = Frame(courseControlFrame, bg=tool_bg)
courseSubFrame = Frame(courseOptionsFrame, bg=check_bg) # Not needed for anything here, but I like the look

Label(courseOptionsFrame, text='Course Options', fg=text_fg, bg=tool_bg).pack(pady=(15,10))

options_entries_dict["flatten_greens"] = tk.BooleanVar()
fGreenCheck = Checkbutton(courseSubFrame, text="Smooth Greens", variable=options_entries_dict["flatten_greens"], fg=check_fg, bg=check_bg)
fGreenCheck.deselect() # This option doesn't make lidar look great, but may play better
options_entries_dict["flatten_fairways"] = tk.BooleanVar()
fFairwayCheck = Checkbutton(courseSubFrame, text="Smooth Fairways", variable=options_entries_dict["flatten_fairways"], fg=check_fg, bg=check_bg)
fFairwayCheck.deselect()
options_entries_dict["auto_elevation"] = tk.BooleanVar()
elevationCheck = Checkbutton(courseSubFrame, text="Auto Elevation Offset", variable=options_entries_dict["auto_elevation"], fg=check_fg, bg=check_bg)
elevationCheck.select() # This option doesn't make lidar look great, but may play better
options_entries_dict["auto_position"] = tk.BooleanVar()
positionCheck = Checkbutton(courseSubFrame, text="Auto Position and Rotate", variable=options_entries_dict["auto_position"], fg=check_fg, bg=check_bg)
positionCheck.deselect()

courseSubFrame.pack(padx=5, pady=5, fill=X, expand=True)
fGreenCheck.grid(row=0, columnspan=2, sticky=W, padx=5)
fFairwayCheck.grid(row=1, columnspan=2, sticky=W, padx=5)
elevationCheck.grid(row=2, columnspan=2, sticky=W, padx=5)
positionCheck.grid(row=3, columnspan=2, sticky=W, padx=5)

# Pack the two option frames side by side
osmControlFrame.pack(side=LEFT, anchor=N, padx=5)
courseOptionsFrame.pack(side=LEFT, anchor=N, padx=5, fill=X, expand=True)

# Pack the big frames side by side
courseControlFrame.pack(side=LEFT, padx=5, pady=5, fill=tk.BOTH, expand=True)
courseConsoleOutput.pack(side=LEFT, padx=5, pady=5, fill=tk.BOTH, expand=True)

root.mainloop()
