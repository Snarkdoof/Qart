# Qart
Sort of QR code using embeddings to detect which picture a phone is looking at. Made to replace QR codes in an art museum.

## Installation

First you need to install a docker enviornment for your server, and then build the img2vec docker image. A GPU is not necessary for this docker.

### Docker image
```
cd environments
./build.sh img2vec

# Test run
docker run --rm img2vec pwd

# Should return "/"
```

### nginx

In order to export the service, we suggest using ngingx or similar to forward https connections to the local Qart service. Suggested configuration below will redirect any request to /qr on the server to the local docker image. Update if you are running it on a different machine, or you want it on a different location.

```
# /etc/nginx/sites-enabled/default or whichever config file you are using

    location /qr {
		proxy_pass http://localhost:8890;
		proxy_http_version 1.1;
		rewrite ^/qr/(.*) /$1 break;
    }

```

### Web page
The qr/index.html must be placed on a public facing web server. Update the "search_url" to point to the Qart service (e.g. the location defined in the nginx file above).

### Data directory

The service needs some files to work. In particular, it needs a set of (relatively small) images to recognize (under 2000x2000 resolution). For each image, a json file should be created with relevant information with the same file name but with .json extension. For example, the file "monalisa.jpg" should have "monalisa.json" with information. The format is:

```
{
	"title": "This is the title of the art piece",
	"intro": "A very short introduction for the first page, like artist, type of work, size, year",
	"audio": ["A list of optional audio files used for background music"], 
	"texts": [
		{
			"title": "Title of detailed bit",
			"text": "Section with more text"
		},
		{
			"img": "url to an image to embed in the text",
			"text": "Text for the image"
		}
	],
	"snd_title": "url to audio file for the title",
	"snd_intro": "url to audio file for the introduction",
	"snd_long": "url to audio file for the longer text"
}

```

In the "texts" part, multiple sections can be provided, using both title, text
and img tags. A tool (create_audio.py) is available to generate the snd_ tags, using online
services to generate audio from text. If these are not given, the built in text to speech of the device is used.


### Creating audio
Using create_audio.py uses service from Microsoft to create possibly more natural sounding voices. In order to use it, a key and region must be provided in the file "config.json", format:
```mo
{
	"key": "your key for asure",
	"region": "your region, e.g. northeurope"
}
```

When this is done, just run ./create_audio.py and the full path to the json file you want processed, e.g. /var/www/html/art/monalisa.json.


## Starting the service

Within the qr directory, the file "run.sh" shows how it can be executed. The directory of the ai.py file must be mapped somewhere, and it must be reflected in the command as well. In the included run.sh file, the ai.py is in the user's home directory, and the command is being run from that directory ($PWD). Also, ensure that the ports are correct, the service listens to port 8890 within the docker, but if you want a different one on the "outside", specify that port first. The data directory must also be mapped as a volume for the service to find the image files.

./run.sh should be executed with -d <directory for the art works as mounted in the docker> -b <URL of the art work & json files online> and -r <the root directory of the files, typically same as the -d directory>

It also supports -p <port> if you don't want it on 8890 for some reason.


# How it works

The service works by creating embeddings for each known image based on an AI
model. When a device on the web wants to identify a piece of art, they point
their camera towards it, and the images are sent periodically to the server
for analysis. It will then calculate the embeddings and measure the cosine
distance between the user's image and the know images. When an image is
guessed, it is returned to the user's device.

It's not known how many different images the Qart service can identify, and
the more similar pieces of art the more difficult it will be to identify them
properly. This needs to be tested.
