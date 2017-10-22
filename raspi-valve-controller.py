#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen
from tornado.websocket import websocket_connect
import datetime
import threading
import json
import croniter
import time
import math
import thread
import urllib2
import uuid
import requests
import RPi.GPIO as GPIO
import Adafruit_Nokia_LCD as LCD
import Adafruit_GPIO.SPI as SPI
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


class Client(object):
    def __init__(self, url, timeout):
        self.url = url
        self.timeout = timeout
        self.ioloop = IOLoop.instance()
        self.ws = None
        
        self.mossbytePayload = None
        self.screen = None
        
        self.isInitialised = False
        
        self.isOnRaspi = True
        self.valveTriggerPin = 3
        self.DC = 23
        self.RST = 24
        self.SPI_PORT = 0
        self.SPI_DEVICE = 0
        self.image = None
        self.draw = None
        self.lastWasKeepAlive = False
        self.timezoneOffsetSeconds = 36000
        
        self.apiKey = 'a28061dc-3a9a-4549-9d6b-0b5354e0af99'
        self.readKey = None
        self.adminKey = None

        self.isDestroying = False
        
        if self.isOnRaspi:
            self.setupGPIO()
            # Hardware SPI usage:
            self.screen = LCD.PCD8544(self.DC, self.RST, spi=SPI.SpiDev(self.SPI_PORT, self.SPI_DEVICE, max_speed_hz=4000000))
            self.screen.clear()
            self.screen.display()
            
            # Initialize library.
            self.screen.begin(contrast=60)
            self.writeScreen((10,10), 'Hello\nJosh')
            time.sleep(5)
	self.readDeviceID()
        if self.isInitialised == True:
            self.connect()
            PeriodicCallback(self.keep_alive, 30000, io_loop=self.ioloop).start()
            self.ioloop.start()

    def destroy(self):
        print '- Destroying...'
        self.isDestroying = True
        if isOnRaspi:
            GPIO.output(self.valveTriggerPin, GPIO.LOW)
            GPIO.cleanup()

    def writeScreen(self, inPosition, inText, clear=True):
        # position (x,y)
        if self.isOnRaspi:
            if clear or self.image == None:
                self.image = Image.new('1', (LCD.LCDWIDTH, LCD.LCDHEIGHT))
                self.draw = ImageDraw.Draw(self.image)
                self.draw.rectangle((0,0,LCD.LCDWIDTH,LCD.LCDHEIGHT), outline=255, fill=255)
            font = ImageFont.load_default()
            self.draw.text(inPosition, str(inText), font=font)
            self.screen.image(self.image)
            self.screen.display()
        
    @gen.coroutine
    def connect(self):
        print '\n- Attempting to establish websocket connection with mossByte...'
        self.writeScreen((0,0), 'Conn...')
        try:
            self.ws = yield websocket_connect(self.url)
        except Exception, e:
            print '- Failed to connect'
            self.writeScreen((0,0), 'neg ws connect')
        else:
            print '- Connected successfully'
            self.writeScreen((0,0), 'pos ws connect')
            self.run()

    def setupGPIO(self):
        if self.isOnRaspi:
	    print '- Setting up GPIO'
	    GPIO.setmode(GPIO.BCM)       # Numbers GPIOs by physical location
            GPIO.setup(self.valveTriggerPin, GPIO.OUT)
            GPIO.output(self.valveTriggerPin, GPIO.LOW)

    @gen.coroutine
    def run(self):
        self.ws.write_message('{"command":"listen","payload":{"key":"'+self.readKey+'"}}')
        self.isSprinklerOn()
        while True:
            print '- Listening for messages'
            msg = yield self.ws.read_message()
            if msg is None:
                print '- Connection seems to have closed'
		self.writeScreen((5,5), 'Conn closed')
                self.ws = None
                break
            else:
                if self.lastWasKeepAlive == False:
                    print '- New message received'
                    jsonStruct = json.loads(msg)
                    if 'payload' in jsonStruct and 'mossbyte' in jsonStruct['payload']:
                        self.mossbytePayload = jsonStruct['payload']['mossbyte'][0]
			self.writeScreen((5,5), self.adminKey)
                else:
                    self.lastWasKeepAlive = False

    def keep_alive(self):
        print '- Sending heartbeat...'
	self.writeScreen((5,5), 'Heartbeat...')
        if self.ws is None:
            self.connect()
        else:
            now = datetime.datetime.now() - datetime.timedelta(seconds=self.timezoneOffsetSeconds)
            now = now.strftime('%Y-%m-%d %H:%M:%S')
            self.ws.write_message('{"command":"heartbeat","payload":{"datetime":"'+now+'"}}')
            self.lastWasKeepAlive = True

    def isSprinklerOn(self):
        self.writeScreen((0,0), 'adminkey')
        if self.isDestroying == False:
            print '\n- Checking valve status'
            threading.Timer(1, self.isSprinklerOn).start()  

            if self.mossbytePayload != None:
                
                print '-- Processing schedule'
                isSprinklerRunning = False

                for schedule in self.mossbytePayload:
                    if 'startTime' in schedule and 'runTime' in schedule and 'months' in schedule and 'daysWeek' in schedule:
                        startTimeSplit = schedule['startTime'].split(':')
                        runTime = int(schedule['runTime'])
                        cronExpression = "%s %s %s %s %s" % (startTimeSplit[1], startTimeSplit[0], '*', ','.join(schedule['months']), ','.join(schedule['daysWeek']))

                        # datetime now
                        now = datetime.datetime.now()

                        # now() - runTime
                        nowSubRunTime = datetime.datetime.now() - datetime.timedelta(minutes=runTime)

                        # find when the next cron would start based on nowSubRunTime
                        cron = croniter.croniter(cronExpression, nowSubRunTime)
                        startTime = cron.get_next()

                        # now convert startTime to a datetime object
                        startTime = datetime.datetime.fromtimestamp(startTime) - datetime.timedelta(seconds=self.timezoneOffsetSeconds)

                        # when will this cron end?
                        endTime = startTime + datetime.timedelta(minutes=runTime)

                        # startTime ------- now ------------ endTime
                        if startTime < now and now < endTime:
                            isSprinklerRunning = True

                self.toggleSprinklerValve(isSprinklerRunning)
                        
    def toggleSprinklerValve(self, isSprinklerRunning):
        if (isSprinklerRunning):
            print '-- Sprinkler valve is OPENED'
            if self.isOnRaspi:
                GPIO.output(self.valveTriggerPin, GPIO.HIGH)
        else:
            print '-- Sprinkler valve is CLOSED'
            if self.isOnRaspi:
                GPIO.output(self.valveTriggerPin, GPIO.LOW)

    def readDeviceID(self):
        with open('read.key', 'a+') as fileDeviceReadKey, open('admin.key', 'a+') as fileDeviceAdminKey:
            fileDeviceReadKey.seek(0)
            fileDeviceAdminKey.seek(0)
            readKey = fileDeviceReadKey.readline()
            adminKey = fileDeviceAdminKey.readline()

            if readKey == "" or adminKey == "":
                self.writeScreen((0,0), 'Keys missing')
                print '- Keys missing'
                
                readKey = str(uuid.uuid1())
                adminKey = str(uuid.uuid1())
                
                print '- Generated keys\nRead: {}\nAdmin: {}'.format(readKey, adminKey)
                
                print '- Requesting new mossByte object'
                
                requestPayload = {"object":[{"jgm":"initialise"}],"keys":{"read":[{"key":readKey,"label":"jgm-read"}],"admin":[{"key":adminKey,"label":"jgm-admin"}]}}
                req = requests.post('https://mossbyte.com/api/v1/{}'.format(self.apiKey), json=requestPayload)        

                if req.status_code == 200:
                    print '- Writing keys to file'
                    fileDeviceReadKey.seek(0)
                    fileDeviceReadKey.write(readKey)
                    fileDeviceAdminKey.seek(0)
                    fileDeviceAdminKey.write(adminKey)
                    
                    print '- Initialisation complete'
                    self.writeScreen((0,0), 'Init complete')
                else:
                    print '- Failed to create mossByte'
                    self.writeScreen((0,0), 'Failed on mossByte')
                    
            else: # !(readKey == "" or adminKey == "")
                print '- Already initialised'
                self.writeScreen((0,0), 'Already init')

            print '- Read: {}\n- Admin: {}\n'.format(readKey, adminKey)
            self.readKey = readKey
            self.adminKey = adminKey
            
            print '- Fetching schedule'
            req = requests.get('https://mossbyte.com/api/v1/{}'.format(self.readKey))
            if req.status_code == 200:
                jsonStruct = json.loads(req.content)
                if 'data' in jsonStruct and 'mossByte' in jsonStruct['data'] and 'object' in jsonStruct['data']['mossByte']:
                    self.mossbytePayload = jsonStruct['data']['mossByte']['object'][0]
                else:
                    self.mossbytePayload = None
                    
                self.isInitialised = True
                self.writeScreen((0,0), 'pos fetch')
            else:
                print '- Failed to fetch schedule'
                self.writeScreen((0,0), 'neg fetch')
                self.isInitialised = False

                
if __name__ == "__main__":
    try:
        client = Client("wss://mossbyte.com:8443", 5)
    except KeyboardInterrupt:  # When 'Ctrl+C' is pressed, the child program destroy() will be  executed.
        client.destroy()
    
