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
        self.isSocketAlive = False

        self.isOnRaspi = True
        self.valveTriggerPin = 17
        self.DC = 23
        self.RST = 24
        self.SPI_PORT = 0
        self.SPI_DEVICE = 0
        self.image = None
        self.draw = None
        self.lastWasKeepAlive = False
        self.timezoneOffsetSeconds = 36000
        self.timeUntilEnding = None
        self.timeUntilStarting = None
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
            pic = Image.open('/home/pi/raspi-valve-controller/jgm.bmp').convert('1')
            self.screen.image(pic)
            self.screen.display()
            #self.writeScreen((10,10), 'Hello\nJosh')
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
        self.writeScreen((0,0), 'Connecting...')
        self.isSocketAlive = False
        try:
            self.ws = yield websocket_connect(self.url)
        except Exception, e:
            print '- Failed to connect'
            self.writeScreen((0,0), 'Failed conn')
        else:
            print '- Connected successfully'
            self.isSocketAlive = True
            self.writeScreen((0,0), 'Connected')
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
                self.isSocketAlive = False
                self.writeScreen((0,0), 'Connection\nclosed.\nReconnecting')
                self.ws = None
                break
            else:
                if self.lastWasKeepAlive == False:
                    print '- New message received'
                    jsonStruct = json.loads(msg)
                    if 'payload' in jsonStruct and 'mossbyte' in jsonStruct['payload']:
                        self.mossbytePayload = jsonStruct['payload']['mossbyte'][0]
                        self.timeUntilStarting = None
                        self.timeUntilEnding = None
                else:
                    self.lastWasKeepAlive = False

    def keep_alive(self):
        print '- Sending heartbeat...'
        self.writeScreen((0,0), 'Heartbeat...')
        if self.ws is None:
            self.connect()
        else:
            now = datetime.datetime.now() - datetime.timedelta(seconds=self.timezoneOffsetSeconds)
            now = now.strftime('%Y-%m-%d %H:%M:%S')
            self.ws.write_message('{"command":"heartbeat","payload":{"datetime":"'+now+'"}}')
            self.lastWasKeepAlive = True

    def isSprinklerOn(self):
        #self.writeScreen((0,0), 'adminkey')
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
                            if self.timeUntilEnding == None or (endTime - now) < self.timeUntilEnding:
                                self.timeUntilEnding = endTime - now
                        else:
                            if self.timeUntilStarting == None or (startTime - now) < self.timeUntilStarting:
                                self.timeUntilStarting = startTime - now

                if len(self.mossbytePayload) == 1:
                    startTime = cron.get_next()
                    startTime = datetime.datetime.fromtimestamp(startTime) - datetime.timedelta(seconds=self.timezoneOffsetSeconds)
                    self.timeUntilStarting = startTime - now

                if isSprinklerRunning == False:
                    self.timeUntilEnding = None

                self.writeMainScreen(isSprinklerRunning) 

                self.toggleSprinklerValve(isSprinklerRunning)
    

    def writeMainScreen(self, isSprinklerRunning):
        nowSec = time.mktime(datetime.datetime.now().timetuple())
        deviceIdString = '{}Device ID: {}'.format(' '*13, self.adminKey)
        self.writeScreen((0,0), deviceIdString[int(0 + nowSec % len(deviceIdString)):int(14 + nowSec % len(deviceIdString))])

        if self.isSocketAlive:
            self.writeScreen((0,10), 'Connected', False)
        else:
            self.writeScreen((0,10), 'No connection', False)

        if self.timeUntilEnding != None:
             strEnd = self.formatSecsToHMS(self.timeUntilEnding.total_seconds())        
        else:
             strEnd = None

        if self.timeUntilStarting != None:
             strStart = self.formatSecsToHMS(self.timeUntilStarting.total_seconds())
        else:
             strStart = None

        self.writeScreen((0,20), 'End:  {}'.format(strEnd), False)
        self.writeScreen((0,30), 'Next: {}'.format(strStart), False)  
        if isSprinklerRunning:
            self.writeScreen((0,40), '.', False)     

    def formatSecsToHMS(self, seconds):
        seconds = int(seconds)
        return '{:02}:{:02}:{:02}'.format(seconds // (60 * 60), seconds % (60 * 60) // 60, seconds % (60))
      
    def toggleSprinklerValve(self, isSprinklerRunning):
        if (isSprinklerRunning):
            print '-- Sprinkler valve is OPENED'
            if self.isOnRaspi:
                GPIO.output(self.valveTriggerPin, GPIO.HIGH)
        else:
            print '-- Sprinkler valve is CLOSED'
            if self.isOnRaspi:
                GPIO.output(self.valveTriggerPin, GPIO.LOW)

    def createMossByte(self):
        readKey = str(uuid.uuid1())
        adminKey = str(uuid.uuid1())
        
        print '- Generated keys\nRead: {}\nAdmin: {}'.format(readKey, adminKey)
        
        print '- Requesting new mossByte object'
        
        requestPayload = {"object":[{"jgm":"initialise"}],"keys":{"read":[{"key":readKey,"label":"jgm-read"}],"admin":[{"key":adminKey,"label":"jgm-admin"}]}}
        connected = False
        while connected == False:
            try:
                req = requests.post('https://mossbyte.com/api/v1/{}'.format(self.apiKey), json=requestPayload)        
                connected = True
            except requests.exceptions.ConnectionError as e:
                time.sleep(5)
        if req.status_code == 200:
            return adminKey, readKey
        else:
            print '- Failed to create mossByte'
            self.writeScreen((0,0), 'Failed on mossByte')
        
    def readDeviceID(self):
        with open('read.key', 'a+') as fileDeviceReadKey, open('admin.key', 'a+') as fileDeviceAdminKey:
            fileDeviceReadKey.seek(0)
            fileDeviceAdminKey.seek(0)
            readKey = fileDeviceReadKey.readline()
            adminKey = fileDeviceAdminKey.readline()

            if readKey == "" or adminKey == "":
                self.writeScreen((0,0), 'Keys missing')
                print '- Keys missing'
                
                adminKey, readKey = self.createMossByte()

                print '- Writing keys to file'
                fileDeviceReadKey.seek(0)
                fileDeviceReadKey.truncate()
                fileDeviceReadKey.write(readKey)
                
                fileDeviceAdminKey.seek(0)
                fileDeviceAdminKey.truncate()
                fileDeviceAdminKey.write(adminKey)
                    
                print '- Initialisation complete'
                self.writeScreen((0,0), 'Init complete')
                
                    
            else: # !(readKey == "" or adminKey == "")
                print '- Already initialised'
                self.writeScreen((0,0), 'Already\ninitialised')

            print '- Read: {}\n- Admin: {}\n'.format(readKey, adminKey)
            self.readKey = readKey
            self.adminKey = adminKey
            
            verifiedReadKey = False
            createMossbyteAttemptMax = 3
            while verifiedReadKey == False and createMossbyteAttemptMax > 0:
                connected = False
                while connected == False:
                    try:
                        print '- Fetching schedule'
                        self.writeScreen((0,0), 'Fetching\nschedule')
                        time.sleep(0.5)
                        req = requests.get('https://mossbyte.com/api/v1/{}'.format(self.readKey))
                        connected = True
                        verifiedReadKey = True
                    except requests.exceptions.ConnectionError as e:
                        self.writeScreen((0,0), 'ConnErr\nTrying again')
                        time.sleep(5)

                if req.status_code == 200:
                    jsonStruct = json.loads(req.content)
                    if 'data' in jsonStruct and 'mossByte' in jsonStruct['data'] and 'object' in jsonStruct['data']['mossByte']:
                        self.mossbytePayload = jsonStruct['data']['mossByte']['object'][0]
                    else:
                        self.mossbytePayload = None
                        
                    self.isInitialised = True
                    self.writeScreen((0,0), 'pos fetch')
                else:
                    self.writeScreen((0,0), req.status_code)
                    time.sleep(3)
                    print '- Failed to fetch schedule'
                    print '- Creating new set of keys'
                    adminKey, readKey = self.createMossByte()
                    createMossbyteAttemptMax = createMossbyteAttemptMax - 1

                    print '- Writing keys to file'
                    fileDeviceReadKey.seek(0)
                    fileDeviceReadKey.truncate()
                    fileDeviceReadKey.write(readKey)
                    
                    fileDeviceAdminKey.seek(0)
                    fileDeviceAdminKey.truncate()
                    fileDeviceAdminKey.write(adminKey)
                    verifiedReadKey = False

                
if __name__ == "__main__":
    try:
        client = Client("wss://mossbyte.com:8443", 5)
    except KeyboardInterrupt:  # When 'Ctrl+C' is pressed, the child program destroy() will be  executed.
        client.destroy()
    
