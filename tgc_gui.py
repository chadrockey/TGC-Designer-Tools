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
from tgc_visualizer import drawCourseAsImage

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

def runLidar(printf):
    global root

    if not root or not hasattr(root, 'filename'):
        alert("Select a course directory before processing lidar files")
        return

    sample_scale = 2.0

    lidar_dir_path = tk.filedialog.askdirectory(initialdir = ".", title = "Select las/laz files directory")
    lidar_map_api.generate_lidar_previews(lidar_dir_path, sample_scale, root.filename, printf=printf)

root = tk.Tk()
root.geometry("800x600")

style = ttk.Style()
style.theme_create( "TabStyle", parent="alt", settings={
        "TNotebook": {"configure": {"tabmargins": [2, 5, 2, 0] } },
        "TNotebook.Tab": {"configure": {"padding": [30, 5] },}})

style.theme_use("TabStyle")

root.title("TGC Golf Tools")

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

## Tools panel
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

## Lidar panel
consoleOutput = tk.scrolledtext.ScrolledText(master=lidar, wrap=tk.WORD, width=20, height=10, state=DISABLED)
printf = partial(tkinterPrintFunction, lidar, consoleOutput)
lidarbutton = Button(lidar, text="Generate Heightmap from Lidar", command=partial(runLidar, printf))

lidarbutton.pack(pady=10)
consoleOutput.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)


root.mainloop()
