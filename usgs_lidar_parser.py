from difflib import SequenceMatcher
import itertools
import json
import laspy
import math
import numpy
import os
from pathlib import Path
import pycrs
import xml.etree.ElementTree as ET

import pyproj
import yaml

from GeoPointCloud import *

def load_usgs_directory(d):
    pc = GeoPointCloud()

    # Add current directory to os path to find laszip-cli for laz files
    os.environ["PATH"] += os.pathsep + os.getcwd() + os.pathsep + 'laszip'

    for filename in os.listdir(d):
        # Only parse laz and las files
        if not filename.endswith('.laz') and not filename.endswith('.las'): continue

        print("Processing: " + filename)

        # Find the XML file with the name closest matching to the las/laz
        highest_match = 0.0
        xml = None
        for x in list(Path(d).glob('*.xml')):
            score = SequenceMatcher(None, str(filename), str(x)).ratio()
            if score > highest_match:
                highest_match = score
                xml = x

        if xml is None:
            print("Could not find metadata for " + filename + ".  Skipping...")
            continue

        print("Using metadata: " + xml.name)
        tree = ET.parse(xml)
        root = tree.getroot()

        # Needed from metadata for all files
        proj = None
        unit = 0.0 # Don't assume unit

        # Get the supplinf tag
        for supplinf in root.iter('supplinf'):
            supp_json = json.loads(supplinf.text.split(';')[0])

            # Parse the .prj contents in the metadata
            try:
                crs = pycrs.parser.from_unknown_text(supp_json['mapProjectionDefinitionField'])
                unit = crs.toplevel.unit.metermultiplier.value
                # Scale the false easting and northing to meters
                # pyproj assumes meters and doesn't convert the falses correctly
                for p in crs.toplevel.params:
                    if p.proj4 == '+x_0' or p.proj4 == '+y_0':
                        p.value *= unit
                proj = pyproj.Proj(crs.to_proj4())
            except:
                pass

        # Look for alternate Metadata formats
        if proj is None:
            # Get the .prj contents
            for c in root.findall('MapProjectionDefinition'):
                crs = pycrs.parser.from_unknown_text(c.text)
                unit = crs.toplevel.unit.metermultiplier.value
                # Scale the false easting and northing to meters
                # pyproj assumes meters and doesn't convert the falses correctly
                for p in crs.toplevel.params:
                    if p.proj4 == '+x_0' or p.proj4 == '+y_0':
                        p.value *= unit
                proj = pyproj.Proj(crs.to_proj4())

        # If unit not in CRS, try to find it in a tag
        if unit == 0.0:
            unit_name = "Unknown"
            for un in itertools.chain(root.iter('plandu'), root.iter('altunits')):
                try:
                    unit_name = un.text.strip() # Some xmls have padded whitespace
                except:
                    pass

            if unit_name == 'meters':
                unit = 1.0
            elif unit_name == 'Foot_US':
                unit = 1200.0/3937.0
            elif unit_name == 'foot': # International Foot
                unit = 0.3048
            else:
                print('Unknown unit: ' + unit_name + ".  Can't process data accurately, please report an issue and send this lidar and metadata")
                unit = 1.0 # Maybe it's meters and we'll get lucky

        # Continue to look for Metadata
        if proj is None:
            # Try to find a UTM zone.
            utm_zone = None
            for uz in root.iter('utmzone'):
                utm_zone = float(uz.text)

            if utm_zone is not None:
                proj = pyproj.Proj(proj='utm', datum='WGS84', ellps='WGS84', zone=utm_zone, units='m')

        # Continue to look for Metadata
        # This last method is the least reliable because the metadata could be hand generated and inconsistent
        if proj is None:
            sys = 'tmerc' # Don't think this newer metadata format uses another system
            datum = 'NAD83'
            ellips = 'GRS80' # Assume this for now, can't find any evidence another is used for lidar
            semiaxis = None
            for sa in root.iter('semiaxis'):
                semiaxis = float(sa.text)
            denflat = None
            for df in root.iter('denflat'):
                denflat = float(df.text)
            sfctrmer = None
            for sfc in root.iter('sfctrmer'):
                sfctrmer = float(sfc.text)
            feast = None
            for fe in root.iter('feast'):
                feast = float(fe.text)*unit # Scale into meters
            fnorth = None
            for fn in root.iter('fnorth'):
                fnorth = float(fn.text)*unit # Scale into meters
            meridian = None
            for m in root.iter('longcm'):
                meridian = float(m.text)
            latprj = None
            for l in root.iter('latprjo'):
                latprj = float(l.text)

            if not None in [semiaxis, denflat, sfctrmer, feast, fnorth, meridian, latprj]:
                proj = pyproj.Proj(proj=sys, datum=datum, ellps=ellips, a=semiaxis, f=denflat, k=sfctrmer, x_0=feast, y_0=fnorth, lon_0=meridian, lat_0=latprj, units='m', axis='enu')

        print("Unit in metadata is " + str(unit))

        # Use laspy to load the point data
        with laspy.file.File(d+"/"+filename, mode='r') as f:
            scaled_x = f.x*unit
            scaled_y = f.y*unit
            scaled_z = f.z*unit

            converted_x = scaled_x
            converted_y = scaled_y
            converted_z = scaled_z

            # Check if coordinate projection needs converted
            if not pc.proj:
                # First dataset will set the coordinate system
                pc.proj = proj
            elif str(pc.proj) != str(proj):
                print("Warning: Data has different projection, re-projecting coordinates.  This may take some time.")
                
                converted_x = []
                converted_y = []
                converted_z = []

                for x, y, z in zip(scaled_x, scaled_y, scaled_z):
                    x2, y2, z2 = pyproj.transform(proj, pc.proj, x, y, z)
                    converted_x.append(x2)
                    converted_y.append(y2)
                    converted_z.append(z2)

            pc.addDataSet(numpy.array(converted_x), numpy.array(converted_y), numpy.array(converted_z), numpy.array(f.intensity), numpy.array(f.classification).astype(int))

    pc.computeOrigin()
    pc.removeBias()
    return pc