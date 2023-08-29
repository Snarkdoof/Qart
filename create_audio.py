#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import re

import azure.cognitiveservices.speech as speechsdk


class TTS:
    def __init__(self, config="config.json"):

        if not os.path.exists(config):
            raise Exception("Missing configuration file '%s'" % config)
        with open(config, "r") as f:
            config = json.load(f)

        # Creates an instance of a speech config with specified subscription key and service region.
        speech_key = config["key"]
        service_region = config["region"]

        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        # Note: the voice setting will not overwrite the voice element in input SSML.
        speech_config.speech_synthesis_voice_name = "nb-NO-FinnNeural"

        # use the default speaker as audio output.
        self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)

        print(dir(self.speech_synthesizer))


    def remove_html_tags(self, text):
        """Remove HTML tags from a string using regular expressions."""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)

    def speak(self, text):

        result = self.speech_synthesizer.speak_text_async(self.remove_html_tags(text)).get()
        # Check result
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("Speech synthesized for text [{}]".format(text))
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print("Error details: {}".format(cancellation_details.error_details))

        return result

    def toFile(self, text, filename):
        """
        We want this as MP3 but we get wav, transcode
        """
        if os.path.exists(filename):
            print("File '%s' already exists, returning" % filename)
            return

        result = self.speak(text)

        fd, name = tempfile.mkstemp()
        os.write(fd, result.audio_data)
        os.sync()

        # Now we transcode
        cmd = ["ffmpeg", "-i", name, filename]
        rv = subprocess.call(cmd)
        if rv != 0:
            raise Exception("ERROR TRANSCODING")

    def addSpeech(self, jsonfile, addToFile=True):
        """
        JSONfile must be formatted for SKMU thing,
        with "title", "intro", "short_text", and "texts".

        For "texts", the titles and image texts are not read.
        """

        with open(jsonfile, "r") as f:
            info = json.load(f)

        if "title" not in info:
            raise Exception("Format of this file seems wrong, missing title")

        # We create separate files
        basename = os.path.splitext(os.path.basename(jsonfile))[0]

        self.toFile(info["title"], basename + "-title.mp3")
        if addToFile:
            info["snd_title"] = basename + "-title.mp3"

        if "intro" in info and info["intro"]:
            t = info["intro"].replace("B:", "Bredde").replace("H:", "Høyde").replace("cm", "centimeter").replace("<br>", ".\n")
            self.toFile(t, basename + "-intro.mp3")
            if addToFile:
                info["snd_intro"] = basename + "-intro.mp3"

        if "short_text" in info and info["short_text"]:
            self.toFile(info["short_text"], basename + "-short_text.mp3")
            if addToFile:
                info["snd_short"] = basename + "-short_text.mp3"

        t = ""
        if "texts" in info:
            for textblock in info["texts"]:
                if "img" in textblock:
                    continue
                t += textblock["text"]
        if t:
            self.toFile(t, basename + "-long_text.mp3")
            if addToFile:
                info["snd_long"] = basename + "-long_text.mp3"

        if addToFile:
            with open(jsonfile, "w") as f:
                json.dump(info, f, indent=" ")

tts = TTS()
import sys
tts.addSpeech(sys.argv[1])
