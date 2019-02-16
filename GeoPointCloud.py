import math
import numpy
import pyproj
import usgs_lidar_parser

# Class for managing the data, base coordinate frame is zero-lower left ENU
# Geo origin is the centroid of the data
class GeoPointCloud:
    def __init__(self):
        self._origin = None
        self.point_matrix = None

        self.resetProperties()

        self._proj = None
        self._platlon = pyproj.Proj(proj='latlong',datum='WGS84')

    def resetProperties(self):
        self._xmin = None
        self._xmax = None
        self._ymin = None
        self._ymax = None
        self._zmin = None
        self._zmax = None
        self._imin = None
        self._imax = None
        self._width = None
        self._height = None
        self._count = None

    def points(self):
        return self.point_matrix

    # Should always be 0.0
    @property
    def xmin(self):
        if self._xmin is None:
            self._xmin =  numpy.amin(self.point_matrix, axis=0)[0]
        return self._xmin

    @xmin.setter
    def xmin(self, xmin):
        self._xmin = xmin

    @property
    def xmax(self):
        if self._xmax is None:
            self._xmax = numpy.amax(self.point_matrix, axis=0)[0]
        return self._xmax

    @xmax.setter
    def xmax(self, xmax):
        self._xmax = xmax

    # Should always be 0.0
    @property
    def ymin(self):
        if self._ymin is None:
            self._ymin = numpy.amin(self.point_matrix, axis=0)[1]
        return self._ymin

    @ymin.setter
    def ymin(self, ymin):
        self._ymin = ymin

    @property
    def ymax(self):
        if self._ymax is None:
            self._ymax = numpy.amax(self.point_matrix, axis=0)[1]
        return self._ymax

    @ymax.setter
    def ymax(self, ymax):
        self._ymax = ymax

    @property
    def zmin(self):
        if self._zmin is None:
            self._zmin = numpy.amin(self.point_matrix, axis=0)[2]
        return self._zmin

    @zmin.setter
    def zmin(self, zmin):
        self._zmin = zmin

    @property
    def zmax(self):
        if self._zmax is None:
            self._zmax = numpy.amax(self.point_matrix, axis=0)[2]
        return self._zmax

    @zmax.setter
    def zmax(self, zmax):
        self._zmax = zmax

    @property
    def imin(self):
        if self._imin is None:
            self._imin = numpy.amin(self.point_matrix, axis=0)[3]
        return self._imin

    @property
    def imax(self):
        if self._imax is None:
            self._imax = numpy.amax(self.point_matrix, axis=0)[3]
        return self._imax

    @property
    def width(self):
        if self._width is None:
            self._width = self.xmax - self.xmin
        return self._width

    @width.setter
    def width(self, width):
        self._width = width

    @property
    def height(self):
        if self._height is None:
            self._height = self.ymax - self.ymin
        return self._height

    @height.setter
    def height(self, height):
        self._height = height

    @property
    def count(self):
        if not self._count:
            if self.point_matrix is None:
                return 0
            self._count = len(self.point_matrix)
        return self._count

    @property
    def proj(self):
        return self._proj

    @proj.setter
    def proj(self, proj):
        self._proj = proj

    # Get lower left of region in projected coordinates
    @property
    def origin(self):
        return self._origin

    @origin.setter
    def origin(self, origin):
        self._origin = origin

    def latLonOrigin(self):
        return self.projToLatLon(self._origin[0], self._origin[1])

    # TODO switch this to lower left and upper right?
    # Would be convenient since origin is lower left
    def ulENU(self):
        return (self.xmin, self.ymax)

    def lrENU(self):
        return (self.xmax, self.ymin)

    def projToENU(self, easting, northing, elevation=None):
        twod = (easting - self._origin[0], northing - self._origin[1])
        if not elevation:
            return twod
        return (twod[0], twod[1], elevation)

    def enuToProj(self, x, y, z=None):
        twod = (x + self._origin[0], y + self._origin[1])
        if not z:
            return twod
        return (twod[0], twod[1], z)

    def latlonToProj(self, lat, lon):
        return pyproj.transform(self._platlon, self.proj, lon, lat) # Lon, lat order

    def projToLatLon(self, easting, northing):
        # pyroj returns easting coordinate, northing coordinate
        lonlat = pyproj.transform(self._proj, self._platlon, easting, northing)
        return (lonlat[1], lonlat[0])

    def enuToLatLon(self, x, y):
        proj = self.enuToProj(x, y)
        return self.projToLatLon(proj[0], proj[1])

    def latlonToENU(self, lat, lon):
        proj = self.latlonToProj(lat, lon)
        return self.projToENU(proj[0], proj[1])

    # Converts ENU coordinates into our specialzed cv2 matrix coordinates
    # The cv2 matrix system is each pixel represents image_scale meters
    # (0,0) is ATYPICAL on the LOWER LEFT corner
    # Plot with matplotlib origin=lower
    @staticmethod
    def enuToCV2(x, y, image_scale):
        # Would use math.floor, but we are always going to have positive values, so usint int for efficiency
        column = int(x / image_scale)
        row = int(y / image_scale)
        return(row, column) # Pixels always use row, column order

    # Converting points to CV2 coordinates one by one is very slow
    # Convert the entire x and y coordinates at once here
    # Returns in ROW, COLUMN order
    def pointsAsCV2(self, image_scale):
        points = self.points()

        # Convert to image indices
        cols = (self.point_matrix[:,0]/image_scale).astype(int)
        rows = (self.point_matrix[:,1]/image_scale).astype(int)

        # Switch to matrix/image order
        points[:,0] = rows
        points[:,1] = cols

        return points

    # Returns coordinates of CENTER of pixel
    @staticmethod
    def cv2ToENU(row, column, image_scale):
        # Pixel centers are offset from coordinates by 1/2 image_scale
        # This conversion loses positional information, so returning the
        # coordinate of pixel centers is the best we can do
        x = (column + 0.5) * image_scale
        y = (row + 0.5) * image_scale
        return (x, y)

    def projToCV2(self, easting, northing, image_scale):
        enu = self.projToENU(easting, northing)
        return self.enuToCV2(enu[0], enu[1], image_scale)

    def cv2ToProj(self, row, column, image_scale):
        enu = self.cv2ToENU(row, column, image_scale)
        return self.enuToProj(enu[0], enu[1])

    def latlonToCV2(self, lat, lon, image_scale, offset_x=0.0, offset_y=0.0):
        enu = self.latlonToENU(lat, lon)
        return self.enuToCV2(enu[0]+offset_x, enu[1]+offset_y, image_scale)

    def cv2ToLatLon(self, row, column, image_scale):
        enu = self.cv2ToENU(row, column, image_scale)
        return self.enuToLatLon(enu[0], enu[1])

    # TODO finish other TGC functions for convenience?
    # TGC Coordinate system is X = easting, Y = generally not used (uses parameters for elevation instead), Z = northing
    def enuToTGC(self, x, y, z):
        # TGC is centered at 0,0
        east_component = x - self.width / 2.0
        north_component = y - self.height / 2.0

        # TGC is X east, Y Down, Z north
        return (east_component, -z, north_component)

    def projToTGC(self, x, y, z):
        enu = self.projToENU(x, y)
        return self.enuToTGC(enu[0], enu[1], z)

    def tgcToENU(self, x, y, z):
        # TGC is centered at 0,0 with X,Z being position and Y being inverted down (largely unused)
        x2 = x + self.width / 2.0
        y2 = z + self.height / 2.0

        return (x2, y2, -y)

    def tgcToCV2(self, x, z, image_scale):
        # TGC is centered at 0,0 with X,Z being position and Y being elevation
        enu = self.tgcToENU(x, 0.0, z)
        return self.enuToCV2(enu[0], enu[1], image_scale)

    def latlonToTGC(self, lat, lon, offset_x=0.0, offset_y=0.0):
        enu = self.latlonToENU(lat, lon)
        return self.enuToTGC(enu[0]+offset_x, enu[1]+offset_y, 0.0)

    def addDataSet(self, newX, newY, newZ, newI, newC):
        newstack = numpy.array((newX, newY, newZ, newI, newC)).transpose()
        if self.point_matrix is None:
            self.point_matrix = newstack
            return
        self.point_matrix = numpy.vstack((self.point_matrix, newstack))

    def addFromImage(self, image, image_scale, latlon_origin, proj):
        # Insert points
        X = []
        Y = []
        Z = []
        I = []
        C = []

        for row in range(0, image.shape[0]):
            for column in range(0, image.shape[1]):
                z = image[row, column]
                if z > 0.1: # Negative and zero values don't get converted into valid points
                    x, y = self.cv2ToENU(row, column, image_scale)
                    X.append(x)
                    Y.append(y)
                    Z.append(z)
                    I.append(0.0)
                    C.append(0.0)

        self.addDataSet(X, Y, Z, I, C)

        # Need to store the lowest coordinates in case we cropped the image by not inserting invalid pixels
        # These will become zero when removeBias() is called and helps center large or offset courses to fit
        # Within the 2k square
        west_most_point = numpy.min(self.point_matrix[:,0]) # Offset from 0.0 left edge to west most point
        south_most_point = numpy.min(self.point_matrix[:,1]) # Offset from 0.0 bottom edge to south most point

        # Calculate the origin of these points
        self._proj = proj
        uncropped_origin = self.latlonToProj(latlon_origin[0], latlon_origin[1])
        # Move the original origin up to the new left/bottom point
        self._origin = (uncropped_origin[0] + west_most_point, uncropped_origin[1] + south_most_point)

        # Clear properties
        self.removeBias()
        self.resetProperties()

    def addFromLatLon(self, lower_left_latlon, upper_right_latlon, printf=print):
        center = ((lower_left_latlon[0]+upper_right_latlon[1])/2.0, (lower_left_latlon[1]+upper_right_latlon[1])/2.0)
        epsg = usgs_lidar_parser.convert_latlon_to_utm_espg(center[0], center[1])
        printf("For center coordinates: " + str(center) + ":")

        self._proj, unit = usgs_lidar_parser.proj_from_epsg(epsg, printf=printf)
        utm_origin = self.latlonToProj(lower_left_latlon[0], lower_left_latlon[1])
        self._origin = utm_origin

        upper_right_utm = self.latlonToProj(upper_right_latlon[0], upper_right_latlon[1])
        self._xmin = 0.0
        self._xmax = upper_right_utm[0] - utm_origin[0]
        self._width = self._xmax
        self._ymin = 0.0
        self._ymax = upper_right_utm[1] - utm_origin[1]
        self._height = self._ymax
        self._zmin = 0.0
        self._zmax = 0.0

    def computeOrigin(self):
        # Estimates the lower left corner as the origin
        # Manually compute origin from data in projected coordinates
        mineasting = numpy.min(self.point_matrix[:,0])
        minnorthing = numpy.min(self.point_matrix[:,1])
        self._origin = (mineasting, minnorthing)

    def removeBias(self):
        self.point_matrix[:,0] = self.point_matrix[:,0] - numpy.min(self.point_matrix[:,0])
        self.point_matrix[:,1] = self.point_matrix[:,1] - numpy.min(self.point_matrix[:,1])
        # No need to clip z to the ground since the tool can do that at the end
        # Helps keep all heights consistent for multiple resolution heightmaps and other features
        #self.point_matrix[:,2] = self.point_matrix[:,2] - numpy.min(self.point_matrix[:,2])
