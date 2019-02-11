# Tutorial

Download and run the exe files from releases: [https://github.com/chadrockey/TGC-Designer-Tools/releases](https://github.com/chadrockey/TGC-Designer-Tools/releases)

The file doesn't need to be installed, just double click it and it should run.

## Getting Lidar Data

United States for now, we may need a wiki for international resources.  Mostly try searching for something like: "Austrailia Lidar LAS" or "Scotland Lidar LAZ"

This is the most difficult part of the process.

Start here: [The NOAA United States Interagency Elevation Inventory](https://coast.noaa.gov/inventory/)

Zoom in on the map to where you want to find Lidar.  This Interagency cooperation will tell you what lidar exists, when it was taken, and where you can get it.

![alt text](https://i.imgur.com/SCT0F2H.png "NOAA Lidar Inventory")

I like to first zoom in useing Basemap->Street, then switch to Basemap->Imagery when I find the golf course.

![alt text](https://i.imgur.com/bEyTqIM.png "Viewing Lidar Data Options")

To view if there's available lidar for this location, first click Identify, then click on your golf course.

Look through the list to find the most recent, available lidar data.  For Muirfield, there's 2018 data not yet published, 2012 you can buy from the State of Ohio, or 2007 data available for free at The National Map.  We'll choose the 2007 data here.

![alt text](https://i.imgur.com/hUryJZT.png "Using the National Map")

Once you follow the link through to the National Map, I like to view USGS Imagery Topo.  Click on the icon that looks like a stack of squares, then select USGS Imagery Topo and zoom into your golf course.

![alt text](https://i.imgur.com/agnNYYh.png "Selecting a Region")

To Make sure we get all of the needed lidar data, draw a square around the golf course by selecting Box, then drawing the box.  Leave enough room that you don't forget a teebox!  (3) Then make sure Lidar Point Cloud is selected, and press (4) Find Products

![alt text](https://i.imgur.com/3CJQTP1.png "Adding Lidar to Cart")

Now you see all of the available lidar files for the box.  In this case, we see data from 2007 and 2006.  Be sure to only select data from the year/set that you chose previously.  Mixing Lidar data does not seem to improve the quality and can have small inconsistencies.  For all of the desired lidar files, click add to cart.  Be sure to scroll down and once you're done, hit view cart.

![alt text](https://i.imgur.com/tpMvvCU.png "Downloading Files from Cart")

Once you're in the cart, usually select download LAS for each file.  This will download the LAS and metadata in a zipped file.

![alt text](https://i.imgur.com/Yx3YjhC.png "Making a Course Directory")

Now on your computer, make a folder that you want to use to store the course files.  In this case< i called it MuirfieldVillage and unzipped all of the lidar zip files into this directory.  You should have at least two files from each zip.

