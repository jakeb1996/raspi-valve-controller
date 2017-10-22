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
#import RPi.GPIO as GPIO
#import Adafruit_Nokia_LCD as LCD
#import Adafruit_GPIO.SPI as SPI

class Client(object):
    def __init__(self, url, timeout):
        self.url = url
        self.timeout = timeout
        self.ioloop = IOLoop.instance()
        self.ws = None
        
        self.mossbytePayload = None
        self.screen = None
        
        self.isInitialised = False
        
        self.isOnRaspi = False
        self.valveTriggerPin = 0
        self.DC = 23
        self.RST = 24
        self.SPI_PORT = 0
        self.SPI_DEVICE = 0
        
        self.lastWasKeepAlive = False
        self.timezoneOffsetSeconds = 36000
        
        self.apiKey = 'a28061dc-3a9a-4549-9d6b-0b5354e0af99'
        self.readKey = None
        self.adminKey = None
        
        self.readDeviceID()

        self.isDestroying = False
        
        if self.isInitialised == True:
            self.connect()
            PeriodicCallback(self.keep_alive, 30000, io_loop=self.ioloop).start()
            self.ioloop.start()

        if self.isOnRaspi:
            # Hardware SPI usage:
            self.screen = LCD.PCD8544(self.DC, self.RST, spi=SPI.SpiDev(self.SPI_PORT, self.SPI_DEVICE, max_speed_hz=4000000))
            self.screen.clear()
            self.screen.display()

            # Initialize library.
            disp.begin(contrast=60)

    def destroy(self):
        self.isDestroying = True
        if isOnRaspi:
            GPIO.output(self.valveTriggerPin, GPIO.LOW)
            GPIO.cleanup()

    def writeScreen(self, text, position, clear=True):
        # position (x,y)
        if self.isOnRaspi:
            font = ImageFont.load_default()
            if clear:
                self.screen.clear()
            draw.text(position, text, font=font)
            self.screen.display()
        
    @gen.coroutine
    def connect(self):
        print '\n- Attempting to establish websocket connection with mossByte...'
        try:
            self.ws = yield websocket_connect(self.url)
        except Exception, e:
            print '- Failed to connect'
        else:
            print '- Connected successfully'
            self.run()

    def setupGPIO(self):
        if isOnRaspi:
            GPIO.setmode(GPIO.BOARD)       # Numbers GPIOs by physical location
            GPIO.setup(self.valveTriggerPin, GPIO.OUT)
            GPIO.output(self.valveTriggerPin, GPIO.HIGH)

    @gen.coroutine
    def run(self):
        self.ws.write_message('{"command":"listen","payload":{"key":"'+self.readKey+'"}}')
        self.isSprinklerOn()
        while True:
            print '- Listening for messages'
            msg = yield self.ws.read_message()
            if msg is None:
                print '- Connection seems to have closed'
                self.ws = None
                break
            else:
                if self.lastWasKeepAlive == False:
                    print '- New message received'
                    jsonStruct = json.loads(msg)
                    if 'payload' in jsonStruct and 'mossbyte' in jsonStruct['payload']:
                        self.mossbytePayload = jsonStruct['payload']['mossbyte'][0]
                else:
                    self.lastWasKeepAlive = False

    def keep_alive(self):
        print '- Sending heartbeat...'
        if self.ws is None:
            self.connect()
        else:
            now = datetime.datetime.now() - datetime.timedelta(seconds=self.timezoneOffsetSeconds)
            now = now.strftime('%Y-%m-%d %H:%M:%S')
            self.ws.write_message('{"command":"heartbeat","payload":{"datetime":"'+now+'"}}')
            self.lastWasKeepAlive = True

    def isSprinklerOn(self):
        if self.isDestroying == False:
            print '\n- Checking valve status'
            threading.Timer(1, self.isSprinklerOn).start()        
            #cronJson = '[{"id":"1507381764425","startTime":"20:45","runTime":"124","daysWeek":["0,1,2,3,4,5,6"],"months":["1,2,3,4,5,6,7,8,9,10,11,12"]},{"id":"1507381777070","startTime":"10:20","runTime":"125","daysWeek":["5"],"months":["1"]},{"id":"1507381956496","startTime":"10:20","runTime":"130","daysWeek":["5"],"months":["1"]},{"id":"1507382743948","startTime":"10:20","runTime":"150","daysWeek":["5"],"months":["1"]},{"id":"1507382857240","startTime":"10:20","runTime":"150","daysWeek":["5"],"months":["7"]},{"id":"1507383607832","startTime":"10:20","runTime":"150","daysWeek":["5"],"months":["7"]},{"id":"1507514478434","startTime":"18:30","runTime":"58","daysWeek":["1","3","5"],"months":["1","3","5","7","9","11"]},{"id":"1507514720515","startTime":"22:00","runTime":"120","daysWeek":["0","1","2","3","4","5","6"],"months":["1","2","3","4","5","6","7","8","9","10","11","12"]}]' 

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
                else:
                    print '- Failed to create mossByte'
                    
            else: # !(readKey == "" or adminKey == "")
                print '- Already initialised'

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
            else:
                print '- Failed to fetch schedule'
                self.isInitialised = False

                
if __name__ == "__main__":
    try:
        client = Client("wss://mossbyte.com:8443", 5)
    except KeyboardInterrupt:  # When 'Ctrl+C' is pressed, the child program destroy() will be  executed.
        client.destroy()
    
