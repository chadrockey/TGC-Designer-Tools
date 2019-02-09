from difflib import SequenceMatcher
import itertools
import json
import laspy
import math
import numpy
import os
import requests
from pathlib import Path
import pycrs
from urllib.request import urlopen, HTTPError
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import pyproj
import yaml

from GeoPointCloud import *

def get_proj_and_unit_from_crs(crs, epsg=None, printf=print):
    unit = crs.toplevel.unit.metermultiplier.value
    # Scale the false easting and northing to meters
    # pyproj assumes meters and doesn't convert the falses correctly
    for p in crs.toplevel.params:
        if p.proj4 == '+x_0' or p.proj4 == '+y_0':
            p.value *= unit
    # Now that we've stored the unit value, set to to 1.0 to work around pyproj bugs
    crs.toplevel.unit.metermultiplier.value = 1.0
    if epsg is not None:
        printf("Overwriting projection with EPSG:" + str(epsg))
        # pyrpoj doesn't like these wkt sometimes, so use the epsg directly
        # But use unit from crs
        proj = pyproj.Proj(init='epsg:'+str(epsg))
    else:
        proj = pyproj.Proj(crs.to_proj4())
    return (proj, unit)

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

def proj_from_epsg(epsg, printf=print):
    # Try to get WKT for these epsg codes from webservices, need this to get a definite value for unit
    epsg_json = requests.get('http://prj2epsg.org/epsg/' + str(epsg) + '.json').json()
    crs = pycrs.parser.from_unknown_text(epsg_json['wkt'])
    return get_proj_and_unit_from_crs(crs, epsg=epsg, printf=printf)

def print_failure_message(printf=print):
    printf("Could not determine lidar projection, please report an issue and send this lidar and metadata")
    printf("Alternatively, look for something called EPSG Value in Metadata and provide EPSG and Conversion to Meters (1.0 for Meters, Approximately 0.3048 for Feet")
    return None

def load_usgs_directory(d, force_epsg=None, force_unit=None, printf=print):
    pc = GeoPointCloud()

    # Add current directory to os path to find laszip-cli for laz files
    os.environ["PATH"] += os.pathsep + os.getcwd() + os.pathsep + 'laszip'

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

            if force_unit is not None:
                unit = float(force_unit)

            # Try to get projection data from laspy
            for v in f.header.vlrs:
                # Parse the .prj contents in the metadata, look for WKT
                try:
                    if proj is not None:
                        break
                    for t in str(v.parsed_body[0]).split('\\n'):
                        try:
                            crs = pycrs.parser.from_unknown_text(t)
                            printf("Found WKT Projection from lidar file")
                            epsg = wkt_to_epsg(t, printf=printf) # Use epsg whenever possible
                            proj, unit = get_proj_and_unit_from_crs(crs, epsg=epsg, printf=printf)
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
                    supp_json = json.loads(supplinf.text.split(';')[0])

                    # Parse the .prj contents in the metadata
                    try:
                        crs = pycrs.parser.from_unknown_text(supp_json['mapProjectionDefinitionField'])
                        printf("Found WKT from metadata file")
                        epsg = wkt_to_epsg(supp_json['mapProjectionDefinitionField'], printf=printf) # Use epsg whenever possible
                        proj, unit = get_proj_and_unit_from_crs(crs, epsg=epsg, printf=printf)
                    except:
                        pass

                # Look for alternate Metadata formats
                if proj is None:
                    # Get the .prj contents
                    for c in root.findall('MapProjectionDefinition'):
                        crs = pycrs.parser.from_unknown_text(c.text)
                        printf("Found PRJ WKT from metadata file")
                        epsg = wkt_to_epsg(c.text, printf=printf) # Use epsg whenever possible
                        proj, unit = get_proj_and_unit_from_crs(crs, epsg=epsg, printf=printf)

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

            printf("Unit in metadata is " + str(unit))
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

    pc.computeOrigin()
    pc.removeBias()
    return pc