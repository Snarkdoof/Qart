#!/usr/bin/env python3
from img2vec_pytorch import Img2Vec
import numpy as np
from scipy import spatial
from PIL import Image
import operator

import os
import pickle
import socketserver
import http.server
import json
import tempfile
import mimetypes
import extcolors


class MyWebServer(socketserver.TCPServer):
    """
    Non-blocking, multi-threaded IPv6 enabled web server
    """
    allow_reuse_address = True


class RequestHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        if (args[1] in ["200", "202"]):
            return
        try:
            API.get_log("NetWatcher").info(format % args)
        except Exception:
            print("Failed to log", format, args)

    def _replyJSON(self, code, msg):
        message = json.dumps(msg).encode("utf-8")
        self.send_response(code)

        self.send_header("Content-Type", "text/json")
        self.send_header("Content-Length", len(message))
        self.send_header("Content-Encoding", "utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")  # TODO: Option this
        self.send_header("Access-Control-Allow-Methods", "POST,OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

        self.end_headers()
        self.wfile.write(message)
        # self.wfile.close()

    def do_OPTIONS(self):
        self.path = self.path.replace("//", "/")
        self._replyJSON(200, {})

    def do_POST(self):
        self.path = self.path.replace("//", "/")

        try:
            data = self.rfile.read(int(self.headers["Content-Length"]))
            if len(data) == 0:
                return self.send_error(500, "Missing body")

            fd, filename = tempfile.mkstemp()
            with open(filename, "wb") as f:
                f.write(data)
                f.close()

            # Now we analyze it
            res = self.imageIdentifier.compare_file(filename)
            self._replyJSON(200, res)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return self.send_error(500, "Internal error")

    def do_GET(self):
        print("GET", self.path)

        if self.path in self.imageIdentifier.known_files:
            # Send file
            with open(self.path, "rb") as f:
                data = f.read()
                ftype = mimetypes.guess_type(self.path)[0]
                self.prepare_send(ftype, len(data))
                self.wfile.write(data)
        else:
            self.failed(404)

    def failed(self, code, message=None):
        """
        Request failed, return error
        """
        try:
            if message:
                self.send_error(code, str(message))
            else:
                self.send_error(code)
        except Exception as e:
            print("Could not send error:", e)
        return False

    def prepare_send(self, type, size=None, response=200, encoding=None, content_range=None, cache=None):
        try:
            self.send_response(response)
        except Exception as e:
            print("Error sending response: %s" % e)
            # self.get_log().warning("Error sending response: %s"%e)
            return

        self.send_header("server", self.server_version)
        if type:
            self.send_header("Content-Type", type)

        self.send_header("Access-Control-Allow-Origin", "*")
        if content_range:
            self.send_header("Content-Range", "bytes %d-%d/%d" % content_range)

        self.send_header("Accept-Ranges", "bytes")
        if size:
            self.send_header("Content-Length", size)
        if encoding:
            self.send_header("Content-Encoding", encoding)
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()


class ImageIdentifier:

    def __init__(self, options):

        self.img2vec = Img2Vec(model="vgg")
        self.options = options
        self.known_files = {}

    def load_directory(self, path, recursive=True):
        """
        Load a directory. Can be called multiple times.
        """
        num_loaded = 0
        for fn in os.listdir(path):
            ext = os.path.splitext(fn.lower())[1]
            if ext in [".jpg", ".png"]:
                self.analyze_file(os.path.join(path, fn))
                num_loaded += 1
            if os.path.isdir(fn) and recursive:
                num_loaded += self.load_directory(os.path.join(path, fn))
        return num_loaded

    def analyze_files(self, filelist):
        for filename in filelist:
            self.analyze_file(filename)

    def analyze_file(self, filename):
        if filename in self.known_files:
            return
        self.known_files[filename] = self._get_features(filename)

        # We also check colors
        colorfile = os.path.splitext(filename)[0] + ".palette"
        if not os.path.exists(colorfile):
            print("Must create color file", colorfile)
            with open(colorfile, "w") as f:
                json.dump(self.get_palette(filename), f)

    def _get_features(self, filename):
        pf = filename + ".features"
        if os.path.exists(pf):
            with open(pf, "rb") as f:
                return pickle.load(f)

        # Get the features
        image = Image.open(filename).convert('RGB')

        vec = self.img2vec.get_vec(image, tensor=True)
        with open(pf, "wb") as f:
            pickle.dump(np.array(vec).squeeze(), f)
        return np.array(vec).squeeze()

    def get_palette(self, path):
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

    def compare_file(self, filename, cutoff=0.4):
        """
        Compare a file to the known files
        """
        features = self._get_features(filename)
        ret = []

        for known_file in self.known_files:
            # Calculate distance
            similarity = 1 - spatial.distance.cosine(self.known_files[known_file], features)
            if similarity > cutoff:
                if options.root:
                    path = known_file.replace(options.root, "")
                else:
                    path = known_file
                path = options.baseurl + path
                ret.append([path, similarity])

        # Order by similarity
        ret.sort(key=operator.itemgetter(1), reverse=True)
        return ret



if __name__ == "__main__":


    from argparse import ArgumentParser
    parser = ArgumentParser(description="WEB service for image QR analysis")

    parser.add_argument("-d", "--dir", dest="dir",
                        default=None,
                        required=True,
                        help="Directory with art")

    parser.add_argument("-b", "--baseurl", dest="baseurl",
                        default=None,
                        required=False,
                        help="Baseurl")

    parser.add_argument("-r", "--root", dest="root",
                        default=None,
                        required=False,
                        help="Root part of directory (removed before adding baseurl)")

    parser.add_argument("-p", "--port", dest="port",
                        default=8890,
                        help="Port for server")

    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except:
        pass  # Not installed, it's ok

    options = parser.parse_args()

    imageIdentifier = ImageIdentifier(options)
    num = imageIdentifier.load_directory(options.dir)
    print("Loaded", num, "files from", options.dir)

    handler = RequestHandler
    handler.imageIdentifier = imageIdentifier

    server = MyWebServer(("", int(options.port)), handler)
    server.serve_forever()
    raise SystemExit()

    known_files = [
        "/home/njaal-local/art/most-famous-paintings-10.jpg",
        "/home/njaal-local/art/most-famous-paintings-11.jpg",
        "/home/njaal-local/art/most-famous-paintings-12.jpg",
        "/home/njaal-local/art/most-famous-paintings-13.jpg",
        "/home/njaal-local/art/most-famous-paintings-15.jpg",
        "/home/njaal-local/art/most-famous-paintings-16.jpg",
        "/home/njaal-local/art/most-famous-paintings-17.jpg",
        "/home/njaal-local/art/most-famous-paintings-18.jpg",
        "/home/njaal-local/art/most-famous-paintings-19.jpg",
        "/home/njaal-local/art/most-famous-paintings-1.jpg",
        "/home/njaal-local/art/most-famous-paintings-20.jpg",
        "/home/njaal-local/art/most-famous-paintings-2.jpg",
        "/home/njaal-local/art/most-famous-paintings-3.jpg",
        "/home/njaal-local/art/most-famous-paintings-4.jpg",
        "/home/njaal-local/art/most-famous-paintings-5.jpg",
        "/home/njaal-local/art/most-famous-paintings-7.jpg",
        "/home/njaal-local/art/most-famous-paintings-8.jpg",
        "/home/njaal-local/art/most-famous-paintings-9.jpg"
    ]

    comp = ImageIdentifier()
    print("Analyzing files")
    comp.analyze_files(known_files)

    import sys
    filename = sys.argv[1]

    print("Evaluating")
    res = comp.compare_file(filename)

    print(res)
