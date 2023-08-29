import extcolors
import sys
import json


def get_palette(path):
    colors, pixel_count = extcolors.extract_from_path(path)

    def make_color_darker(rgb_tuple, target_lightness):
        # We subtract a given percentage of each channel
        darker_tuple = tuple(min(255, max(0, round(i*target_lightness))) for i in rgb_tuple)
        return darker_tuple

    ret = []
    for color in colors:
        if sum(color[0]) < 200:
            continue  # Too dark
        if sum(color[0]) > 600:
            continue  # Too light
        ret.append({"actual": "#%02x%02x%02x" % color[0],
                    "light": "#%02x%02x%02x" % make_color_darker(color[0], 1 + sum(color[0])/(1485.)),
                    "dark": "#%02x%02x%02x" % make_color_darker(color[0], sum(color[0])/(1485.)),
                    "sum": sum(color[0])})
    return ret

ret = get_palette(sys.argv[1])
print(json.dumps(ret))