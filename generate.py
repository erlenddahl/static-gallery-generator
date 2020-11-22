import os
import json
import copy
import imghdr
from PIL import Image, ImageDraw
from pathlib import Path

forceRegenerate = False

with open('config.json', 'r') as f:
    config = json.load(f)

config["fileTypes"] = [x.lower() for x in config["fileTypes"]]

class GalleryItem:

	def __init__(self, path, albumId, id):
		self.path = path
		self.albumId = albumId
		self.id = id
		self.url = path.as_posix()
		self.title = path.name
		self.description = ""
		self.extraData = {}

		(self.displayPath, self.width, self.height, self.thumbPath, self.tWidth, self.tHeight, self.dominantColor) = processItem(path)

	def setMetadata(self, data):

		for key in data:

			if key == "title":
				self.title = data[key]
			elif key == "description":
				self.description = data[key]
			else:
				self.extraData[key] = data[key]

	def getItemJson(self):

		return {
			"src": self.displayPath.as_posix(),
			"srct": self.thumbPath.as_posix(),
			"width": self.width,
			"height": self.height,
			"imgtWidth": self.tWidth,
			"imgtHeight": self.tHeight,
			"imageDominantColor": self.dominantColor,
			"downloadURL": self.url,
			"title": self.title,
			"ID": str(self.albumId) + "-" + str(self.id),
			"albumID": str(self.albumId)
		}

	def getAlbumJson(self):
		
		return {
			"src": self.url,
			"title": self.title,
			"description": self.description,
			"ID": str(self.albumId),
			"kind": "album"
		}


def isValidFileType(file):

	for ft in config["fileTypes"]:
		if file.name.lower().endswith(ft):
			return True

	return False

def getThumbnailPath(photoPath, height = None, prefix = None):

	if prefix is None:
		prefix = str(height) + "px-"

	thumbPath = photoPath.parent / config["dataFolder"] / (prefix + photoPath.name)
	return thumbPath

def generateImageThumbnail(photoPath, thumbPath, height):

	image = Image.open(photoPath)
	image.thumbnail((99999, height), Image.ANTIALIAS)
	image.save(thumbPath)

def getDominantColor(image):
	image.resize((1,1))
	rgb_im = image.convert('RGB')
	r, g, b = rgb_im.getpixel((0,0))
	return '#%02x%02x%02x' % (r, g, b)

def extractVideoFrame(videoPath):

	framePath = getThumbnailPath(videoPath, prefix="frame-")
	framePath = framePath.parent / (framePath.name + ".jpg")

	if not forceRegenerate and framePath.is_file():
		return framePath

	frameExtractionCommand = config["movieFrameExtraction"].replace("{MOVIE_PATH}", str(videoPath)).replace("{OUTPUT_PATH}", str(framePath))
	os.system(frameExtractionCommand)

	im = Image.open(framePath)
	draw = ImageDraw.Draw(im, 'RGBA')
	width, height = im.size
	
	r = config["thumbHeight"] * 0.15 * (height / config["thumbHeight"])
	x = width / 2
	y = height / 2
	draw.ellipse([(x-r, y-r), (x+r, y+r)], fill=(0, 0, 0, 170))

	r /= 2
	draw.polygon([(x-r*0.8, y-r), (x-r*0.8, y+r), (x+r, y)], fill=(255, 255, 255, 170))

	im.save(framePath)

	return framePath

def processImage(photoPath, thumbPath, isVideoFrame=False):

	displayPath = photoPath
	im = Image.open(photoPath)
	width, height = im.size
	if not isVideoFrame and height > config["displayHeight"]:
		displayPath = getThumbnailPath(photoPath, config["displayHeight"])
		if forceRegenerate or not displayPath.is_file():
			generateImageThumbnail(photoPath, displayPath, config["displayHeight"])

	if forceRegenerate or not thumbPath.is_file():
		generateImageThumbnail(photoPath, thumbPath, config["thumbHeight"])

	im = Image.open(thumbPath)
	tWidth, tHeight = im.size
	dominantColor = getDominantColor(im)

	return (displayPath, width, height, thumbPath, tWidth, tHeight, dominantColor)

def processItem(itemPath):

	thumbPath = getThumbnailPath(itemPath, config["thumbHeight"])

	thumbPath.parent.mkdir(parents=True, exist_ok=True)

	# imghdr returns None if not an image, or the image type (for example "jpeg")
	imageType = imghdr.what(itemPath)

	if imageType is not None: # This is an image file

		return processImage(itemPath, thumbPath)

	else: # This is a video file

		framePath = extractVideoFrame(itemPath)
		thumbPath = thumbPath.parent / (thumbPath.name + ".jpg")

		d = processImage(framePath, thumbPath, True)

		# Must convert to list to be able to change the first element, then back to tuple.
		d = list(d)
		d[0] = itemPath
		d = tuple(d)
		return d


items = []

for (albumId, album) in [(i, f) for (i, f) in enumerate(Path(config["galleryLocation"]).iterdir(), 1) if f.is_dir()]:

	photos = [GalleryItem(f, albumId, i) for (i, f) in enumerate(album.iterdir(), 1) if f.is_file() and isValidFileType(f)]

	albumDataFile = album / "album.json"
	albumData = {}
	if albumDataFile.is_file():
		albumData = json.loads(albumDataFile.read_text(encoding=config["metadataEncoding"] if "metadataEncoding" in config else None))

	cover = copy.deepcopy(photos[0])

	if "coverImage" in albumData:
		for photo in photos:
			if photo.path.name == albumData["coverImage"]:
				cover = copy.deepcopy(photo)
				cover.setMetadata(albumData)
				break

	# TODO: Metadata encoding
	# TODO: Read item metadata from [itemname].json
	# TODO: Set exif data?

	items.append(cover.getAlbumJson())

	for photo in photos:
		items.append(photo.getItemJson())


with open(config["htmlTemplate"], 'r') as f:
	html = f.read()
	
html = html.replace("{ITEMS_HERE}", json.dumps(items))
html = html.replace("{THUMB_HEIGHT_HERE}", str(config["thumbHeight"]))

with open(config["outputFile"], 'w') as f:
	f.write(html)