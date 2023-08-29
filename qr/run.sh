#!/bin/sh

PWD=`pwd`
docker run --rm  -it --gpus all -v /home:/home -v /var/www:/var/www -p 8890:8890 img2vec $PWD/ai.py -p 8890 $@
