
# Record types of surfaces
surfaces = {
    0: "bunker",
    1: "green",
    2: "fairway",
    3: "rough",
    4: "heavyrough",
    5: "clearobjects",
    6: "cleartrees",
    7: "surface1",
    8: "surface2",
    9: "water",
    10: "surface3"
}

featuresToSurfaces = {
    "bunker": 0,
    "green": 1,
    "fairway": 2,
    "rough": 3,
    "heavyrough": 4,
    "clearobjects": 5,
    "cleartrees": 6,
    "surface1": 7,
    "surface2": 8,
    "water": 9,
    "surface3": 10,
    "cartpath": 10,
}

brushes = {
    8: "firm_circle",
    9: "medium_circle",
    10: "soft_circle",
    15: "soft_square",
    54: "very_soft_circle",
    72: "hard_square",
    73: "hard_circle"
}

themes = {
    #0: "old_rustic",
    #1: "old_swiss"
    2: "Desert",
    #3: "old_autumn",
    #4: "old_hightlands",
    5: "Boreal",
    6: "Tropical",
    7: "Countryside",
    8: "Harvest",
    9: "Winter",
    10: "Delta",
    11: "Rustic",
    12: "Swiss",
    13: "Steppe",
    14: "Autumn",
    15: "Highlands",
    16: "TPC Sawgrass",
    17: "Atlantic Beach Country Club",
    18: "TPC Boston",
    19: "TPC Deere Run",
    20: "TPC Scottsdale",
    21: "TPC Southwind",
    22: "TPC Summerlin",
    #23: "boreal_alternate"
}

normal_trees = {
    2: [0, 1, 2, 3, 9],
    5: [0, 1],
    6: [0, 1, 2, 3, 4, 5, 6, 7],
    7: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16],
    8: [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
    10: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12],
    11: [0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    12: [0, 1, 3, 4, 7, 8, 10],
    13: [0, 1, 2, 3, 4, 5, 6, 7],
    14: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    15: [0, 1, 6, 7],
}

skinny_trees = {
    2: [10, 11, 12, 13, 14, 15, 16],
    5: [3, 4, 5, 9, 10, 11, 12, 13, 14, 15, 16],
    6: [8, 9, 13, 14, 15, 16, 17, 18, 19],
    7: [13, 14],
    8: [0, 1, 2],
    10: [],
    11: [13, 14, 16],
    12: [2, 5, 9],
    13: [8, 9, 10, 11, 12, 13, 14, 15],
    14: [12, 15],
    15: [2, 3, 8, 9, 10, 22],
}

tee_colors = {
    4: "red",
    0: "green",
    3: "white",
    2: "blue",
    1: "black",
    5: "gold"
}
