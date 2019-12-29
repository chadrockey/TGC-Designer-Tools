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
import string

import tgc_definitions
import tgc_tools
import lidar_map_api
import tgc_image_terrain
from tgc_visualizer import drawCourseAsImage
import OSMTGC

TGC_GUI_VERSION = "0.3.0"

image_width = 500
image_height = 500

# Make placeholder image
data=numpy.array(numpy.random.random((image_width,image_height))*100,dtype=int)
iim=Image.frombytes('L', (data.shape[1],data.shape[0]), data.astype('b').tostring())

root = None
canvas = None
canvas_image = None
course_json = None

scorecard = None
inner_frame = None # Scorecard inner frame

def drawPlaceholder():
    global root
    global canvas
    global canvas_image
    default_im = ImageTk.PhotoImage(image=iim)
    canvas.itemconfig(canvas_image, image = default_im)
    root.update()

def scorecardSumList(l):
    front = 0
    back = 0
    total = 0
    output = []
    for i in range(0, len(l)):
        value = math.ceil(l[i])
        total += value
        if i < 9:
            front += value
        else:
            back += value
        output.append(value)
        if i == 8:
            output.append(front)
    if back > 0:
        output.append(back)
    output.append(total)

    return output

def drawScorecard(course_json):
    global scorecard
    global inner_frame

    # Which Tkinter colors to draw on the chart
    hole_color = "snow"
    par_color = "bisque"
    pin_color = "gray40"
    tee_color_order = course_json["teeColours"]
    tee_colors_dict = {
        "red":"firebrick1",
        "white":"floral white",
        "blue":"navy",
        "black":"gray10",
        "green":"dark green",
        "gold":"gold"
    }
    tee_text_colors_dict = {
        "red":"black",
        "white":"black",
        "blue":"white",
        "black":"white",
        "green":"white",
        "gold":"black"
    }

    # Determine tee colors for chart
    tee_colors = []
    tee_text_colors = []
    for color in tee_color_order:
        color_name = tgc_definitions.tee_colors[color]
        tee_colors.append(tee_colors_dict[color_name])
        tee_text_colors.append(tee_text_colors_dict[color_name])

    # Clear the chart each time the course is redrawn
    if inner_frame is not None:
        inner_frame.destroy()
    inner_frame = Frame(scorecard, bg="darkgrey")
    inner_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

    # Par and yardages values from holes
    pars, pin_counts, tees = tgc_tools.get_hole_information(course_json)

    # Determine number of valid tee sets
    # And fill in missing information for tees that weren't placed
    valid_tees = []
    for tee in tees:
        empty_tee = all(v is None for v in tee)
        if not empty_tee:
            valid_tees.append(tee)
    
    for i in range(0, len(pars)):
        last_valid_distance = 0.0
        for j in range(0, len(valid_tees)):
            if valid_tees[j][i] is not None:
                last_valid_distance = valid_tees[j][i]
            else:
                valid_tees[j][i] = last_valid_distance

    scorecard_pars = scorecardSumList(pars)
    scorecard_tees = []
    for t in valid_tees:
        scorecard_tees.append(scorecardSumList(t))

    # Generate top holes label and pin counts
    holes = []
    pins = []
    for i in range(0, len(pars)):
        holes.append(i+1)
        pins.append(pin_counts[i])
        if i == 8:
            holes.append("out")
            pins.append("")
    if len(pars) > 9:
        holes.append("in")
        pins.append("")
    holes.append("tot")
    pins.append("")

    h = Entry(inner_frame, justify='center', fg="black", readonlybackground=hole_color, width=10)
    h.insert(0, "HOLE")
    h.configure(state="readonly")
    h.grid(row=0, column=0)

    h = Entry(inner_frame, justify='center', fg="black", readonlybackground=par_color, width=10)
    h.insert(0, "PAR")
    h.configure(state="readonly")
    h.grid(row=1, column=0)

    h = Entry(inner_frame, justify='center', fg="black", readonlybackground=pin_color, width=10)
    h.insert(0, "NUM PINS")
    h.configure(state="readonly")
    h.grid(row=2, column=0)

    for j in range(0, len(scorecard_tees)):
        h = Entry(inner_frame, justify='center', fg=tee_text_colors[j], readonlybackground=tee_colors[j], width=10)
        h.insert(0, "TEE SET")
        h.configure(state="readonly")
        h.grid(row=3+j, column=0)

    for i in range(0, len(holes)):
        # Append hole numbers
        h = Entry(inner_frame, justify='center', fg="black", readonlybackground=hole_color, width=5)
        h.insert(0, str(holes[i]))
        h.configure(state="readonly")
        h.grid(row=0, column=i+1)

        # Append par values
        p = Entry(inner_frame, justify='center', fg="black", readonlybackground=par_color, width=5)
        p.insert(0, str(scorecard_pars[i]))
        p.configure(state="readonly")
        p.grid(row=1, column=i+1)

        # Append number of pins - useful for working around simulator bug
        p = Entry(inner_frame, justify='center', fg="black", readonlybackground=pin_color, width=5)
        p.insert(0, str(pins[i]))
        p.configure(state="readonly")
        p.grid(row=2, column=i+1)

        # Append yardages
        for j in range(0, len(scorecard_tees)):
            p = Entry(inner_frame, justify='center', fg=tee_text_colors[j], readonlybackground=tee_colors[j], width=5)
            p.insert(0, str(scorecard_tees[j][i]))
            p.configure(state="readonly")
            p.grid(row=3+j, column=i+1)

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

    drawScorecard(cjson)
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
            name_entry.configure(state='normal')
            course_name_var.set(course_json["name"])
            course_theme_number = course_json["theme"]
            course_theme_var.set(tgc_definitions.themes[course_theme_number])
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

    # Also support children directly outside of a frame
    if len(frame.winfo_children()) == 0:
        if var.get(): # Check enabled
            frame['state'] = 'normal'
        else:
            frame['state'] = 'disable'

def validateCourseName(action_type, index, value, previous, new_text, validation_types, validation_type, widget_name):
    if len(value) > 32:
        return False
    return True
    # Looks like they accept almost all characters, wow...
    '''allowed_chars = string.ascii_letters + string.digits + ' '
    allowed_set = set(allowed_chars)
    valid = all(x in allowed_set for x in new_text)
    if not valid:
        return False
        course_name_var.set(previous)
    return True'''

course_types = [
    ('Golf Course Files', '*.course'), 
    ('All files', '*'), 
]

def setCourseTheme(name1, name2, op):
    global course_theme_var
    global course_json
    if course_json is not None:
        theme_index_list = list(tgc_definitions.themes.keys())
        theme_list = list(tgc_definitions.themes.values())
        new_course_theme = int(theme_index_list[theme_list.index(course_theme_var.get())])
        course_json["theme"] = new_course_theme

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
        name_entry.configure(state='normal')
        course_name_var.set(course_json["name"])
        course_theme_number = course_json["theme"]
        course_theme_var.set(tgc_definitions.themes[course_theme_number])
        drawCourse(course_json)

def exportCourseAction():
    global root
    global course_json

    if not root or not hasattr(root, 'filename'):
        alert("Select a course directory before exporting a .course file")
        return

    if course_json is None:
        alert("Make sure to import a .course file")
        return

    dest_file = tk.filedialog.asksaveasfilename(title='Save Course As', defaultextension='.course', initialdir=root.filename, confirmoverwrite=True, filetypes=course_types)

    if dest_file:
        new_course_name = course_name_var.get()
        if len(new_course_name) > 0:
            course_json["name"] = new_course_name
            # Need to update the metadata file or it won't show up right in the course list
            tgc_tools.set_course_metadata_name(root.filename, course_json["name"])
        theme_index_list = list(tgc_definitions.themes.keys())
        theme_list = list(tgc_definitions.themes.values())
        new_course_theme = int(theme_index_list[theme_list.index(course_theme_var.get())])
        course_json["theme"] = new_course_theme
        drawPlaceholder()
        tgc_tools.pack_course_file(root.filename, None, dest_file, course_json)
        drawCourse(course_json)

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
numpy_terrain_types = [
    ('Golf Course Terrain', '*.terrain.npy'), 
    ('All files', '*'), 
]
numpy_holes_types = [
    ('Golf Course Holes', '*.holes.npy'), 
    ('All files', '*'), 
]

def separateAction(stype="terrain"):
    global course_json
    if stype == "terrain":
        name = "Terrain"
        f = tgc_tools.strip_terrain
        ext = ".terrain.npy"
        filetypes = numpy_terrain_types
    elif stype == "holes":
        name = "Holes"
        f = tgc_tools.strip_holes
        ext = ".holes.npy"
        filetypes = numpy_holes_types
    else:
        print("No action taken: Unknown separate type: " + stype)
        return

    dest_file = tk.filedialog.asksaveasfilename(title=name+' filename', defaultextension=ext, initialdir=root.filename, confirmoverwrite=True, filetypes=filetypes)

    if dest_file:
        drawPlaceholder()
        course_json = f(course_json, dest_file)
        drawCourse(course_json)

def insertAction(stype="terrain"):
    global course_json
    if stype == "terrain":
        name = "Terrain"
        f = tgc_tools.insert_terrain
        ext = ".terrain.npy"
        filetypes = numpy_terrain_types
    elif stype == "holes":
        name = "Holes"
        f = tgc_tools.insert_holes
        ext = ".holes.npy"
        filetypes = numpy_holes_types
    else:
        print("No action taken: Unknown insert type: " + stype)
        return

    input_file = tk.filedialog.askopenfilename(title=name+' filename', defaultextension=ext, initialdir=root.filename, filetypes=filetypes)

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

def rightClickMenu(e):
    try:
        def rClick_Copy(e, apnd=0):
            e.widget.event_generate('<Control-c>')

        def rClick_CopyAll(e, apnd=0):
            e.widget.event_generate('<Control-a>')
            e.widget.event_generate('<Control-c>')

        e.widget.focus()

        nclst=[('Copy', lambda e=e: rClick_Copy(e)),
               ('Copy All', lambda e=e: rClick_CopyAll(e))]

        rmenu = Menu(None, tearoff=0, takefocus=0)

        for (txt, cmd) in nclst:
            rmenu.add_command(label=txt, command=cmd)

        rmenu.tk_popup(e.x_root+40, e.y_root+10,entry="0")

    except TclError:
            pass

    return "break"

def tkinterPrintFunction(root, textfield, message):
    textfield.configure(state='normal')
    textfield.insert(tk.END, message + "\n")
    textfield.configure(state='disabled')
    textfield.see(tk.END)
    textfield.bind('<Button-3>', rightClickMenu, add='')
    root.update()

def runLidar(scale_entry, epsg_entry, printf):
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

    lidar_dir_path = tk.filedialog.askdirectory(initialdir=root.filename, title="Select las/laz files directory")
    if lidar_dir_path:
        lidar_map_api.generate_lidar_previews(lidar_dir_path, sample_scale, root.filename, force_epsg=force_epsg, printf=printf)

def generateCourseFromLidar(options_entries_dict, printf):
    global root
    global course_json

    if not root or not hasattr(root, 'filename'):
        alert("Select a course directory before processing heightmap file")
        return

    if course_json is None:
        alert("Make sure to import a .course file")
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

osm_types = [
    ('Open Street Map Exports', '*.osm'), 
    ('All files', '*'), 
]
def importOSMFile(options_entries_dict, printf):
    global root
    global course_json

    if not root or not hasattr(root, 'filename'):
        alert("Select a course directory before importing OSM Flat Course")
        return

    if course_json is None:
        alert("Make sure to import a .course file")
        return

    # There may be many options for this in the future (which splines to add, clear splines?, flatten fairways/greens, etc) so store efficiently
    options_dict = {}

    # Snapshot the current values of the entries dictionary into the options_dict
    # We are reusing the same keys, so try not to change them often
    # All values in the entries_dict must support the get() function
    for key, entry in options_entries_dict.items():
        options_dict[key] = entry.get()

    osm_file = tk.filedialog.askopenfilename(title='Select your OpenStreetMap Export', defaultextension='osm', initialdir=root.filename, filetypes=osm_types)
    if osm_file:
        with open(osm_file, encoding="utf8") as f:
            xml_data = f.read()
            printf("Loading OpenStreetMap Data from " + str(osm_file))
            drawPlaceholder()
            course_json = tgc_image_terrain.generate_flat_course(course_json, xml_data, options_dict=options_dict, printf=printf)
            drawCourse(course_json)
            printf("Done Rendering Course Preview")

root = tk.Tk()
root.geometry("800x650")

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
scorecard = ttk.Frame(nb, style='new.TFrame')
nb.pack(fill=BOTH, expand=1)
nb.add(tools, text='Course Tools')
nb.add(lidar, text='Process Lidar')
nb.add(course, text='Import Terrain and Features')
nb.add(scorecard, text="Scorecard")

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

name_frame = Frame(tool_buttons_frame, bg=tool_bg)
Label(name_frame, text="Name", fg=text_fg, bg=tool_bg).pack(side=LEFT, padx=5)
course_name_var = tk.StringVar()
name_entry = tk.Entry(name_frame,textvariable=course_name_var, width=32, justify='left', validate="key")
name_entry['validatecommand'] = (name_entry.register(validateCourseName), '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')
name_entry.configure(state='disabled')
name_entry.configure(disabledbackground="grey50")
name_entry.pack(side=LEFT, padx=10, pady=5)
name_frame.pack(pady=5)

theme_list = list(tgc_definitions.themes.values())
theme_frame = Frame(tool_buttons_frame, bg=tool_bg)
Label(theme_frame, text="Theme", fg=text_fg, bg=tool_bg).pack(side=LEFT, padx=5)
course_theme_var = tk.StringVar()
course_theme_var.trace("w", setCourseTheme)
course_theme_var.set(theme_list[0])
theme_option = tk.OptionMenu(theme_frame, course_theme_var, *theme_list)
theme_option.config(width=25)
theme_option.pack(side=LEFT, padx=10, pady=5)
theme_frame.pack(pady=5)

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

terrain_frame = Frame(tool_buttons_frame, bg=bg_color)
stb = Button(terrain_frame, text="Separate Terrain", command=partial(separateAction, "terrain"))
stb.pack(side=LEFT, padx=5, pady=5)
itb = Button(terrain_frame, text="Insert Terrain File", command=partial(insertAction, "terrain"))
itb.pack(side=LEFT, pady=5)
terrain_frame.pack()

holes_frame = Frame(tool_buttons_frame, bg=bg_color)
shb = Button(holes_frame, text="Separate Holes", command=partial(separateAction, "holes"))
shb.pack(side=LEFT, padx=5, pady=5)
ihb = Button(holes_frame, text="Insert Holes File", command=partial(insertAction, "holes"))
ihb.pack(side=LEFT, pady=5)
holes_frame.pack()

ccb = Button(tool_buttons_frame, text="Combine Course Directory", command=combineAction)
ccb.pack(pady=5)

default_im = ImageTk.PhotoImage(image=iim)
canvas_image = canvas.create_image(0,0,image=default_im,anchor=tk.NW)
root.update()

## Lidar Tab
lidarConsoleOutput = tk.scrolledtext.ScrolledText(master=lidar, wrap=tk.WORD, width=20, height=10, state=DISABLED)
lidarPrintf = partial(tkinterPrintFunction, lidar, lidarConsoleOutput)

lidarControlFrame = Frame(lidar, bg=tool_bg)

scale_label = Label(lidarControlFrame, text="Map Scale", fg=text_fg, bg=tool_bg)
scale_entry = tk.Entry(lidarControlFrame, width=8, justify='center')
scale_entry.insert(END, 2.0)
epsg_label = Label(lidarControlFrame, text="Force Lidar EPSG Projection", fg=text_fg, bg=tool_bg)
epsg_entry = tk.Entry(lidarControlFrame, width=8, justify='center')
epsg_entry.insert(END, "")
lidarbutton = Button(lidarControlFrame, text="Select Lidar and Generate Heightmap", command=partial(runLidar, scale_entry, epsg_entry, lidarPrintf))

scale_label.pack(side=LEFT, padx=5)
scale_entry.pack(side=LEFT, padx=5)
epsg_label.pack(side=LEFT, padx=5)
epsg_entry.pack(side=LEFT, padx=5)
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
waterCheck = Checkbutton(osmSubFrame, text="Import Water", variable=options_entries_dict["water"], fg=check_fg, bg=check_bg)
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
osm_hole_filter = tk.Entry(osmSubFrame, width=10, justify='center')
options_entries_dict["hole_name_filter"] = osm_hole_filter
options_entries_dict["building"] = tk.BooleanVar()
buildingCheck = Checkbutton(osmSubFrame, text="Import Buildings", variable=options_entries_dict["building"], fg=check_fg, bg=check_bg)
buildingCheck.select()
options_entries_dict["tree"] = tk.BooleanVar()
treeCheck = Checkbutton(osmSubFrame, text="Import Mapped Woods/Trees", variable=options_entries_dict["tree"], fg=check_fg, bg=check_bg)
treeCheck.deselect()
osmbutton = Button(osmSubFrame, text="Make Flat Course From OSM File", command=partial(importOSMFile, options_entries_dict, coursePrintf))

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
Label(osmSubFrame, text="Match Hole Names", fg=check_fg, bg=check_bg).grid(row=12, sticky=W, padx=5)
osm_hole_filter.grid(row=12, column=1, padx=5)
buildingCheck.grid(row=13, columnspan=2, sticky=W, padx=5)
treeCheck.grid(row=14, columnspan=2, sticky=W, padx=5)
osmbutton.grid(row=15, columnspan=2)

useOSMCheck.pack(padx=10, pady=10)
osmSubFrame.pack(padx=5, pady=5)

coursebutton = Button(courseControlFrame, text="Select and Import Heightmap and OSM into Course", command=partial(generateCourseFromLidar, options_entries_dict, coursePrintf))

# Pack the controls frames, button at the top followed by the options
coursebutton.pack(padx=10, pady=10)

# Other Course Options
courseOptionsFrame = Frame(courseControlFrame, bg=tool_bg)
courseSubFrame = Frame(courseOptionsFrame, bg=check_bg) # Not needed for anything here, but I like the look

Label(courseOptionsFrame, text='Course Options', fg=text_fg, bg=tool_bg).pack(pady=(15,10))

options_entries_dict["auto_elevation"] = tk.BooleanVar()
elevationCheck = Checkbutton(courseSubFrame, text="Auto Elevation Offset", variable=options_entries_dict["auto_elevation"], fg=check_fg, bg=check_bg)
elevationCheck.select() # This option doesn't make lidar look great, but may play better
options_entries_dict["auto_position"] = tk.BooleanVar()
positionCheck = Checkbutton(courseSubFrame, text="Auto Position and Rotate", variable=options_entries_dict["auto_position"], fg=check_fg, bg=check_bg)
positionCheck.deselect()
options_entries_dict["add_background"] = tk.BooleanVar()
backgroundCheck = Checkbutton(courseSubFrame, text="Add Background Terrain/Remove Cliffs", variable=options_entries_dict["add_background"], fg=check_fg, bg=check_bg)
backgroundCheck.deselect()
bgentry = tk.Entry(courseSubFrame, width=10, justify='center')
bgentry.insert(END, '16.0')
options_entries_dict["background_scale"] = bgentry
backgroundCheck['command'] = partial(disableAllChildren, options_entries_dict["add_background"], bgentry)
options_entries_dict["lidar_trees"] = tk.BooleanVar()
lidarTreeCheck = Checkbutton(courseSubFrame, text="Add Trees From Lidar (Experimental)", variable=options_entries_dict["lidar_trees"], fg=check_fg, bg=check_bg)
lidarTreeCheck.deselect()
options_entries_dict["tree_variety"] = tk.BooleanVar()
treeVarietyCheck = Checkbutton(courseSubFrame, text="Tree Variety (Lidar and OSM)", variable=options_entries_dict["tree_variety"], fg=check_fg, bg=check_bg)
treeVarietyCheck.deselect()
options_entries_dict["fill_water"] = tk.BooleanVar()
fillWaterCheck = Checkbutton(courseSubFrame, text="Fill Holes Under Blue Mask", variable=options_entries_dict["fill_water"], fg=check_fg, bg=check_bg)
fillWaterCheck.deselect()
options_entries_dict["purge_water"] = tk.BooleanVar()
purgeWaterCheck = Checkbutton(courseSubFrame, text="Remove All Terrain Under Blue Mask", variable=options_entries_dict["purge_water"], fg=check_fg, bg=check_bg)
purgeWaterCheck.deselect()

# Pack the osmControlFrame
courseSubFrame.pack(padx=5, pady=5, fill=X, expand=True)
elevationCheck.grid(row=0, columnspan=2, sticky=W, padx=5)
positionCheck.grid(row=1, columnspan=2, sticky=W, padx=5)
backgroundCheck.grid(row=2, columnspan=2, sticky=W, padx=5)
Label(courseSubFrame, text="Background Scale", fg=check_fg, bg=check_bg).grid(row=3, column=0, sticky=W, padx=5)
bgentry.grid(row=4, column=1, sticky=W, padx=5)
lidarTreeCheck.grid(row=5, columnspan=2, sticky=W, padx=5)
treeVarietyCheck.grid(row=6, columnspan=2, sticky=W, padx=5)
fillWaterCheck.grid(row=7, columnspan=2, sticky=W, padx=5)
purgeWaterCheck.grid(row=8, columnspan=2, sticky=W, padx=5)

# Pack the two option frames side by side
osmControlFrame.pack(side=LEFT, anchor=N, padx=5)
courseOptionsFrame.pack(side=LEFT, anchor=N, padx=5, fill=X, expand=True)

# Pack the big frames side by side
courseControlFrame.pack(side=LEFT, padx=5, pady=5, fill=tk.BOTH, expand=True)
courseConsoleOutput.pack(side=LEFT, padx=5, pady=5, fill=tk.BOTH, expand=True)

root.mainloop()
