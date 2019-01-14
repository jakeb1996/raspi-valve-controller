# Raspi Valve Controller
A method for controlling Raspberry Pi GPIO pins via websockets.

## Dependencies
- Please review the Python import headers for dependencies.
- [Raspi-Valve Control Panel](https://github.com/jakeb1996/raspi-valve-remote-control)

## Software & Hardware Requirements
- Raspberry Pi 3B & Micro SD Card
- [WinSCP](https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet)
- [Putty](http://www.putty.org/)
- 1kOhm resister
- 5v-12v 5-pin Relay
- 12V DC Solenoid
- 12V DC Power supply (minimum 1A)
- BC548 Transistor
- Diode
- Nokia 5110 
- DC-DC 12v-5v voltage regulator
- Veroboard, wire, solder, etc

## Circuitry 
![alt text](http://www.susa.net/wordpress/wp-content/uploads/2012/06/Relay-Sample.png "Raspberry Pi Relay Circuit")

![alt text](https://docs.microsoft.com/en-us/windows/iot-core/media/pinmappingsrpi/rp2_pinout.png "Raspberry Pi 3B Pins")

## Installation
1) Install [Raspian](https://www.raspberrypi.org/downloads/) on the Raspi
1) Connect the Raspi to your network
2) Transfer the `raspi-valve-controller.py` script to the Raspi
3) Execute the script

Optional:
1) Setup the script to run as a service on startup
2) Google a generic init.d tutorial