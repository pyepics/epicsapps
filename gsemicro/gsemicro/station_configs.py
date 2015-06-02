station_configs = {}

# store station configurations in json strings:
#
#  group label,  prec, max_step, motorlist: [[pvname, desc, direction], ...]
#
statiosn_configs['MICROSCOPE_13IDE'] = '''
[["XY Stages",  3, 50,  [["13IDE:m1", "x", 1], ["13IDE:m2", "y", 1]]],
 ["Focus",      3, 10,  [["13IDE:m3", "z", 1]]],
]
'''

station_configs['STATION_13BMD'] = '''
[["XY Stages",  3, 50,  [["13BMD:m4", "x", 1], ["13BMD:m6", "y", 1]]],
 ["Focus",      3, 10,  [["13BMD:m5", "z", 1]]],
]
'''
station_configs['STATION_13IDE'] = '''
[["Fine Stages",   4,  2, [["13XRM:m1", "finex",  1], ["13XRM:m2", "finey", -1]]],
 ["Coarse Stages", 3, 50, [["13XRM:m4", "x",      1], ["13XRM:m6", "y",      1]]],
 ["Focus",         3, 10, [["13XRM:m5", "z",      1]]],
 ["Theta",         3,  9, [["13XRM:m3", "theta",  1]]]
]
'''
