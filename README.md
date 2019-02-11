# TGC-Designer-Tools

Tools to support course creation and Lidar/Terrain Creation in The Golf Club 2019.

To say thanks and leave a tip for this software if it's saved you hundreds of hours: [https://www.paypal.me/chaddev](https://www.paypal.me/chaddev)

For ongoing course requests, priority support or feature requests, I've opened a Patreon for this project: [https://www.patreon.com/chadgolf](https://www.patreon.com/chadgolf)

Patreon is a subscription model that allows communication and continuing support between creators and their communities.

## Windows EXE Download

Github is intended for software developers.  If you just want to run the software, view the latest releases here: [https://github.com/chadrockey/TGC-Designer-Tools/releases](https://github.com/chadrockey/TGC-Designer-Tools/releases)

Developers and others can look through and run the code.  The main entry points are tgc_gui, lidar_map_api, and tgc_image_terrain.

------

Shameless plug: I work primarily as a software consultant.  If you or your company need electronics, sensors, data processing, automation or robotics expertise, feel free to send inquiries to chad@chadev.com.  I'm part of a medium sized team and we've worked for many businesses you're familiar with, and we have a long history of success.

![3D Course View](https://i.imgur.com/vVPcNBh.png)

![Green Slopes with Bunker](https://i.imgur.com/VazhLEU.png)

![User Interface](https://i.imgur.com/4GnzENd.png)

## Software Developer Installation

Currently targeting Python 3.7

Get the dependencies with:

python -m pip install -r requirements.txt

## Distribution

pyinstaller -F --add-binary="./laszip/laszip-cli.exe;laszip" tgc_gui.py

