import alsaaudio
import json
import os.path
import os
import pycurl
import requests
import re
import sys
import time

from creds import *
from pocketsphinx.pocketsphinx import *
from requests.packages.urllib3.exceptions import *
from sphinxbase.sphinxbase import *
from StringIO import StringIO
from threading import Thread

# Avoid warning about insure request
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

# Start pulseaudio daemon
os.system('sudo -H -u debian pulseaudio --start')
os.system("echo 'connect 43:88:48:B8:62:1A' | bluetoothctl")
time.sleep(5)

# Set up Notification LEDs
os.system('echo out > /sys/class/gpio/gpio57/direction')
os.system('echo out > /sys/class/gpio/gpio58/direction')
os.system('echo out > /sys/class/gpio/gpio59/direction')
os.system('echo out > /sys/class/gpio/gpio60/direction')
os.system('echo out > /sys/class/gpio/gpio52/direction')
os.system('echo 1 > /sys/class/gpio/gpio57/value')
os.system('echo 1 > /sys/class/gpio/gpio58/value')
os.system('echo 1 > /sys/class/gpio/gpio59/value')
os.system('echo 1 > /sys/class/gpio/gpio60/value')
os.system('echo 1 > /sys/class/gpio/gpio52/value')

time.sleep(2)
os.system('echo 0 > /sys/class/gpio/gpio57/value')
os.system('echo 0 > /sys/class/gpio/gpio58/value')
os.system('echo 0 > /sys/class/gpio/gpio59/value')
os.system('echo 0 > /sys/class/gpio/gpio60/value')
os.system('echo 0 > /sys/class/gpio/gpio52/value')


# ------ Start User configuration settings --------
sphinx_data_path = "/root/pocketsphinx/"
modeldir = sphinx_data_path+"/model/"
datadir = sphinx_data_path+"/test/data"

recording_file_path = "/root/beagleman/"
filename=recording_file_path+"/myfile.wav"
filename_raw=recording_file_path+"/myfile.pcm"

# Personalize the robot :)
username = "Franklin"

# Trigger phrase. Pick a phrase that is easy to save repeatedly the SAME way
# seems by default a single syllable word is better
trigger_phrase = "dog"

# ----- End User Configuration -----

# PocketSphinx configuration
config = Decoder.default_config()

# Set recognition model to US
config.set_string('-hmm', os.path.join(modeldir, 'en-us/en-us'))
config.set_string('-dict', os.path.join(modeldir, 'en-us/cmudict-en-us.dict'))

#Specify recognition key phrase
config.set_string('-keyphrase', trigger_phrase)
config.set_float('-kws_threshold',1)

# Hide the VERY verbose logging information
config.set_string('-logfn', '/dev/null')

path = os.path.realpath(__file__).rstrip(os.path.basename(__file__))

# Read microphone at 16 kHz. Data is signed 16 bit little endian format.
inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE)
inp.setchannels(1)
inp.setrate(16000)
inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
inp.setperiodsize(1024)

token = None
recording_file = None

start = time.time()

# Determine if trigger word/phrase has been detected
record_audio = False

# Process audio chunk by chunk. On keyword detected perform action and restart search
decoder = Decoder(config)
decoder.start_utt()

# Using slightly outdated urlib3 software by default. But disable harmless warning
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

# All Alexa code based on awesome code from AlexaPi
# https://github.com/sammachin/AlexaPi

# Verify that the user is connected to the internet
def internet_on():
	print "Checking Internet Connection"
	try:
		r =requests.get('https://api.amazon.com/auth/o2/token')
	        print "Connection OK"
		return True
	except:
		print "Connection Failed"
		return False

#Get Alexa Token
def gettoken():
	global token
	refresh = refresh_token
	if token:
		return token
	elif refresh:
		payload = {"client_id" : Client_ID, "client_secret" : Client_Secret, "refresh_token" : refresh, "grant_type" : "refresh_token", }
		url = "https://api.amazon.com/auth/o2/token"
		r = requests.post(url, data = payload)
		resp = json.loads(r.text)
		token = resp['access_token']
		return token
	else:
		return False
		
def alexa():
	url = 'https://access-alexa-na.amazon.com/v1/avs/speechrecognizer/recognize'
	headers = {'Authorization' : 'Bearer %s' % gettoken()}
        # Set parameters to Alexa request for our audio recording
	d = {
   		"messageHeader": {
       		"deviceContext": [
           		{
               		"name": "playbackState",
               		"namespace": "AudioPlayer",
               		"payload": {
                   		"streamId": "",
        			   	"offsetInMilliseconds": "0",
                   		"playerActivity": "IDLE"
               		}
           		}
       		]
		},
   		"messageBody": {
       		"profile": "alexa-close-talk",
       		"locale": "en-us",
       		"format": "audio/L16; rate=44100; channels=1"
   		}
	}

        # Send our recording audio to Alexa
	with open(filename_raw) as inf:
		files = [
				('file', ('request', json.dumps(d), 'application/json; charset=UTF-8')),
				('file', ('audio', inf, 'audio/L16; rate=44100; channels=1'))
				]	
		r = requests.post(url, headers=headers, files=files)
        print r
	if r.status_code == 200:
		print "Debug: Alexa provided a response"

		for v in r.headers['content-type'].split(";"):
			if re.match('.*boundary.*', v):
				boundary =  v.split("=")[1]
		data = r.content.split(boundary)
                for d in data:
			if (len(d) >= 1024):
				audio = d.split('\r\n\r\n')[1].rstrip('--')
                # Write response audio to response.mp3 may or may not be played later
		with open(path+"response.mp3", 'wb') as f:
			f.write(audio)
	else:
		print "Debug: Alexa threw an error with code: ",r.status_code

def offline_speak(string):
	os.system('espeak -ven-uk -p50 -s140 "'+string+'" > /dev/null 2>&1')



def web_service():

	# Call the two speech recognitions services in parallel
	alexa_thread = Thread( target=alexa, args=() )
	alexa_thread.start()
	alexa_thread.join()

    # Play Alexa response
	os.system('sudo -H -u debian play -c 1 -r 24000 -q response.mp3')
                #os.system('sudo -H -u debian play  -c 1 -r 24000 -q {}response.mp3  > /dev/null 2>&1'.format(path))
	time.sleep(.5)
		

while internet_on() == False:
	print "."

offline_speak("Hello "+username+", Ask me any question")

print "Debug: Ready to receive request"
while True:
	try:
		# Read from microphone
		l,buf = inp.read()
	except:
                # Hopefully we read fast enough to avoid overflow errors
		print "Debug: Overflow"
		continue

        #Process microphone audio via PocketSphinx only when trigger word
        # hasn't been detected
	if buf and record_audio == False:
		decoder.process_raw(buf, False, False)

	# Detect if keyword/trigger word was said
	if record_audio == False and decoder.hyp() != None:
                # Trigger phrase has been detected
                
        #LED start
		os.system('echo 1 > /sys/class/gpio/gpio57/value')
		os.system('echo 1 > /sys/class/gpio/gpio58/value')
		os.system('echo 1 > /sys/class/gpio/gpio59/value')
		os.system('echo 1 > /sys/class/gpio/gpio60/value')
		os.system('echo 1 > /sys/class/gpio/gpio52/value')
        
        
		record_audio = True
		start = time.time()

                # To avoid overflows close the microphone connection
		inp.close()

                # Open file that will be used to save raw micrphone recording
		recording_file = open(filename_raw, 'w')
		recording_file.truncate()

                # Indicate that the system is listening to request
                offline_speak("Yes")

                # Reenable reading microphone raw data
		inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE)
		inp.setchannels(1)
		inp.setrate(16000)
		inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
		inp.setperiodsize(1024)

		print ("Debug: Start recording")


	# Only write if we are recording
	if record_audio == True:
		recording_file.write(buf)

	# Stop recording after 5 seconds
	if record_audio == True and time.time() - start > 5:
		#LED stop
		os.system('echo 0 > /sys/class/gpio/gpio52/value')
		os.system('echo 0 > /sys/class/gpio/gpio57/value')
		os.system('echo 0 > /sys/class/gpio/gpio58/value')
		os.system('echo 0 > /sys/class/gpio/gpio59/value')
		os.system('echo 0 > /sys/class/gpio/gpio60/value')
		print ("Debug: End recording")
		record_audio = False

		# Close file we are saving microphone data to
		recording_file.close()

		# Convert raw PCM to wav file (includes audio headers)
		os.system("sox -t raw -r 16000 -e signed -b 16 -c 1 "+filename_raw+" "+filename+" && sync")

		print "Debug: Sending audio to services to be processed"
		# Send recording to our speech recognition web services
		web_service()

		# Now that request is handled restart audio decoding
		decoder.end_utt()
		decoder.start_utt()
