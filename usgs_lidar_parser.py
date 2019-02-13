from difflib import SequenceMatcher
import itertools
import json
import laspy
import math
import numpy
import os
import requests
from pathlib import Path
from urllib.request import urlopen, HTTPError
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import pyproj

from GeoPointCloud import *

def wkt_to_epsg(wkt, printf=print):
    '''
    Function borrowed from https://github.com/cmollet/sridentify, don't want or need the local database aspects
    Copyright 2018 Cory Mollet

    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
    '''
    url = 'http://prj2epsg.org/search.json?'
    params = {
        'mode': 'wkt',
        'terms': wkt
    }
    try:
        req = urlopen(url + urlencode(params))
    except HTTPError as http_exc:
        printf("""Failed to retrieve data from prj2epsg.org API:\n
                        Status: %s \n
                        Message: %s""" % (http_exc.code, http_exc.msg))
    else:
        raw_resp = req.read()
        try:
            resp = json.loads(raw_resp.decode('utf-8'))
        except json.JSONDecodeError:
            printf('API call succeeded but response\
                    is not JSON: %s' % raw_resp)
            return None

        return int(resp['codes'][0]['code'])
    return None

def get_unit_multiplier_from_epsg(epsg):
    # Can't find any lightweight way to do this, but I depend heavily on pyproj right now
    # Until there's a better way, get the unit by converting (1,0) from 'unit' to 'meter'
    meter_proj = pyproj.Proj(init='epsg:'+str(epsg), preserve_units=False) # Forces meter
    unit_proj = pyproj.Proj(init='epsg:'+str(epsg), preserve_units=True) # Stays in native unit
    try:
        # Due to numerical precision and the requirements for foot vs survey foot
        # Use a larger number for the transform
        scale_value = 1.0e6
        x2, y2 = pyproj.transform(unit_proj, meter_proj, scale_value, 0.0)
        return x2/scale_value
    except:
        pass
    return 0.0

# Some of the epsgs found in lidar files don't represent projected coordinate systems
# but are instead the datum or other geographic reference systems
def is_epsg_datum(epsg):
    # It looks like these are all in the 4000 to 42NN range.
    # I can't determine which are valid, so I'm going to convert from meters to degrees
    # If it's degrees to degrees, it won't modify the number
    # The coordinate systems we will look for are limited between -180.0 and 180.0 output
    meter_proj = pyproj.Proj(init='epsg:'+str(epsg), preserve_units=False) # Forces meter
    degree_proj = pyproj.Proj(proj='latlong', datum='WGS84')
    try:
        scale_value = 1.0e6
        x2, y2 = pyproj.transform(meter_proj, degree_proj, scale_value, 0.0)
        return math.isclose(scale_value, x2, abs_tol=1.0) # Should be very different
    except:
        pass
    return True # Invalidate this EPSG if it can't be determined or used

def get_proj_and_unit_from_wkt(wkt, printf=print):
    epsg = wkt_to_epsg(wkt, printf=printf) # Use epsg whenever possible
    if is_epsg_datum(epsg):
        # Not the right kind of coordinate reference system
        printf("EPSG is not map projection, skipping: " + str(epsg))
        return None, 0.0
    if epsg is not None:
        printf("Overwriting projection with EPSG:" + str(epsg))
        proj = pyproj.Proj(init='epsg:'+str(epsg))
        unit = get_unit_multiplier_from_epsg(epsg)
        return (proj, unit)
    printf("EPSG not found for WKT: \n" + wkt + "\n")
    return None, 0.0

def proj_from_epsg(epsg, printf=print):
    # Try to get WKT for these epsg codes from webservices, need this to get a definite value for unit
    epsg_json = requests.get('http://prj2epsg.org/epsg/' + str(epsg) + '.json').json()
    return get_proj_and_unit_from_wkt(epsg_json['wkt'], printf=printf)

def print_failure_message(printf=print):
    printf("Could not determine lidar projection, please report an issue and send this lidar and metadata")
    printf("Alternatively, look for something called EPSG Value in Metadata and provide EPSG and Conversion to Meters (1.0 for Meters, Approximately 0.3048 for Feet")
    return None

def load_usgs_directory(d, force_epsg=None, force_unit=None, printf=print):
    pc = GeoPointCloud()

    # Add current directory to os path to find laszip-cli for laz files
    os.environ["PATH"] += os.pathsep + os.getcwd()
    # Add ./laszip
    os.environ["PATH"] += os.pathsep + "." + os.sep + 'laszip'
    # Add {this_file_location}/laszip for Pyinstaller temp directories
    os.environ["PATH"] += os.pathsep + os.path.dirname(os.path.realpath(__file__)) + os.sep + 'laszip'

    for filename in os.listdir(d):
        # Only parse laz and las files
        if not filename.endswith('.laz') and not filename.endswith('.las'): continue

        printf("Processing: " + filename)

        # Use laspy to load the point data
        with laspy.file.File(d+"/"+filename, mode='r') as f:
            # Needed from metadata for all files
            proj = None
            unit = 0.0 # Don't assume unit

            if force_epsg is not None:
                proj, unit = proj_from_epsg(force_epsg, printf=printf)

            # Try to get projection data from laspy
            for v in f.header.vlrs:
                # Parse the .prj contents in the metadata, look for WKT
                try:
                    if proj is not None:
                        break
                    for t in str(v.parsed_body[0]).split('\\n'):
                        try:
                            proj, unit = get_proj_and_unit_from_wkt(t, printf=printf)
                            if proj is not None:
                                printf("Found WKT Projection from lidar file")
                                break
                        except:
                            pass
                except:
                    pass

                # Look for GEOTIFF tags or something?  This is a list of values and EPSG codes
                if proj is None and v.parsed_body is not None and len(v.parsed_body) > 3:
                    try:
                        num_records = v.parsed_body[3]
                        for i in range(0, num_records):
                            key = v.parsed_body[4 + 4*i]
                            value_offset = v.parsed_body[7 + 4*i]
                            try:
                                proj, unit = proj_from_epsg(value_offset, printf=printf)
                                if proj is not None:
                                    printf("Found EPSG from lidar file: " + str(value_offset))
                                    break
                            except:
                                pass
                    except:
                        pass

                # Projection coordinates list
                if proj is None and v.parsed_body and len(v.parsed_body) == 10:
                    # (0.0, 500000.0, 0.0, -75.0, 0.9996, 1.0, 6378137.0, 298.2572221010042, 0.0, 0.017453292519943278)
                    # pyproj.Proj('+proj=tmerc +datum=NAD83 +ellps=GRS80 +a=6378137.0 +f=298.2572221009999 +k=0.9996 +x_0=500000.0 +y_0=0.0 +lon_0=-75.0 +lat_0=0.0 +units=m +axis=enu ', preserve_units=True)
                    try:
                        sys = 'tmerc' # Don't think any other format is used
                        datum = 'NAD83'
                        ellips = 'GRS80' # Assume this for now, can't find any evidence another is used for lidar
                        proj = pyproj.Proj(proj=sys, datum=datum, ellps=ellips, a=v.parsed_body[6], f=v.parsed_body[7], k=v.parsed_body[4], \
                                           x_0=v.parsed_body[1], y_0=v.parsed_body[0], lon_0=v.parsed_body[3], lat_0=v.parsed_body[2], units='m', axis='enu')
                        unit = v.parsed_body[5]
                        printf("Found Projection parameters from lidar file")
                    except:
                        pass

            # Wasn't in the las files, look for a prj file
            if proj is None:
                # Find the PRJ file with the name closest matching to the las/laz
                highest_match = 0.0
                prj = None
                for x in list(Path(d).glob('*.prj')):
                    score = SequenceMatcher(None, str(filename), str(x)).ratio()
                    if score > highest_match:
                        highest_match = score
                        prj = x

                if prj is not None:
                    printf("Using PRJ file: " + prj.name)

                    try:
                        with open(prj, mode='r') as p:
                            proj, unit = get_proj_and_unit_from_wkt(p.read(), printf=printf)
                            if proj is not None:
                                printf("Found WKT Projection from PRJ file")
                    except:
                        printf("Could not parse: " + prj)
                        pass

            # Wasn't in the las files, do the difficult search in metadata xmls
            if proj is None:
                # Find the XML file with the name closest matching to the las/laz
                highest_match = 0.0
                xml = None
                for x in list(Path(d).glob('*.xml')):
                    score = SequenceMatcher(None, str(filename), str(x)).ratio()
                    if score > highest_match:
                        highest_match = score
                        xml = x

                if xml is None:
                    printf("Could not find metadata for " + filename + ".  Skipping...")
                    continue

                printf("Using metadata: " + xml.name)
                tree = ET.parse(xml)
                root = tree.getroot()

                # Get the supplinf tag
                for supplinf in root.iter('supplinf'):
                    try:
                        supp_json = json.loads(supplinf.text.split(';')[0])
                    except json.JSONDecodeError:
                        printf("Could not load supplinf")

                    # Parse the .prj contents in the metadata
                    try:
                        proj, unit = get_proj_and_unit_from_wkt(supp_json['mapProjectionDefinitionField'], printf=printf)
                        printf("Found WKT from metadata file")
                    except:
                        pass

                # Look for alternate Metadata formats
                if proj is None:
                    # Get the .prj contents
                    for c in root.findall('MapProjectionDefinition'):
                        proj, unit = get_proj_and_unit_from_wkt(c.text, printf=printf)
                        printf("Found PRJ WKT from metadata file")

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
                        return print_failure_message(printf=printf)

                # Continue to look for Metadata
                if proj is None:
                    # Try to find a UTM zone.
                    utm_zone = None
                    for uz in root.iter('utmzone'):
                        utm_zone = float(uz.text)

                    if utm_zone is not None:
                        printf("Found UTM Zone from metadata file")
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
                        printf("Found Projection Parameters from metadata file")
                        proj = pyproj.Proj(proj=sys, datum=datum, ellps=ellips, a=semiaxis, f=denflat, k=sfctrmer, x_0=feast, y_0=fnorth, lon_0=meridian, lat_0=latprj, units='m', axis='enu')

            if proj is None:
                return print_failure_message(printf=printf)

            # Need to overwrite unit last for situations where projection is not overwritten
            if force_unit is not None:
                unit = float(force_unit)

            printf("Unit in use is " + str(unit))
            printf("Proj4 : " + str(proj))

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
                printf("Warning: Data has different projection, re-projecting coordinates.  This may take some time.")
                
                converted_x = []
                converted_y = []
                converted_z = []

                for x, y, z in zip(scaled_x, scaled_y, scaled_z):
                    x2, y2, z2 = pyproj.transform(proj, pc.proj, x, y, z)
                    converted_x.append(x2)
                    converted_y.append(y2)
                    converted_z.append(z2)

            pc.addDataSet(numpy.array(converted_x), numpy.array(converted_y), numpy.array(converted_z), numpy.array(f.intensity), numpy.array(f.classification).astype(int))

    if not pc.count:
        printf("No valid lidar files found, no action taken")
        printf("Directory was: " + d)
        return None

    pc.computeOrigin()
    pc.removeBias()
    return pc