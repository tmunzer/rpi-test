
"""
-------------------
HOW TO INSTALL

NOTE: the installation process can be done with a RPI3 (it's easier to get it connected to the newtork). Once finished,
you can shutdown the RPI3 and move the SDCARD to a RPI Zero

1. USB SSH
1.1 add the following line at the end of /boot/config.txt
dtoverlay=dwc2

1.2 Add the following text JUST AFTER rootwait in /boot/cmdline.txt
modules-load=dwc2,g_ether

2. Use rapi-config to enable the camera (Interface > Camera > Enable) then reboot

3. Copy the script on the RPi (you can use scp)

4. Install the script with `sudo python3 ./qrcode_script.py -i` (The RPi should be connected to internet to load
the required packages). This will update the os, install the packages and python modules, register the script as 
a service, enable the script at boot, and start the script

HOW TO USE 
-------------------
1. Start the RPI

2. When the LED is solid, push the button to enter the configuration mode. the LED with blink Yellow (it should) for a few 
seconds (the RPi is loading the required libraries) then it sould become solid yellow when it's ready to scan the QRCode
(the camera LED should also be ON)
NOTE: You can exit the configuration mode by pressing the button a new time. The RPi will also automatically exit the
configuration mode after 60sec

3. Scan the QRCode

NOTE: You can remove "/etc/wpa_supplicant/wpa_supplicant.conf" and reboot the RPi to get it in "default" mode (which 
means, not connected to the Wi-Fi, and waiting to be configured)

DEFAULT LED COLORS
-------------------
Green [solid]: system loaded and script starting
Purple [solid]: Wi-Fi not configured
Yellow [blink]: entering the configuration mode
Yellow [solid]: configuration mode
White [solid]: connected to the Wi-Fi
"""


import logging
import sys
import getopt
import RPi.GPIO as GPIO
import time
import re
import os
import subprocess
from datetime import datetime, timedelta
########################################################################
########################
# CONFIGRATION
led_pins = {'pin_R': 37, 'pin_B': 38, 'pin_G': 40}  # pins is a dict
but_pins = 33
wpa_supplicant_conf = "/etc/wpa_supplicant/wpa_supplicant.conf"
wpa_suppliant_ctrl = "DIR=/var/run/wpa_supplicant GROUP=netdev"
wpa_supplicant_country = "FR"

########################
# COLORS
color_configured = 0xFF00FF
color_started = 0x00FF00
color_connected = 0xFFFFFF
color_configured_mode = 0xFFFF00
#red = 0xFF0000
freq = 500


########################################################################
########################
# LOGGER
logging.basicConfig(filename='/var/log/qrcode_script.log', level=logging.DEBUG)
logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)-6s - %(levelname)-8s %(message)s (%(funcName)s)')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

########################################################################
########################
# QRCODE REGEX
qrcode_re = r"WIFI:S:(.*);T:WPA;P:(.*);;"

########################################################################
########################
# LED CONFIG
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)       # Numbers GPIOs by physical location
for i in led_pins:
    GPIO.setup(led_pins[i], GPIO.OUT)   # Set pins' mode is output
    GPIO.output(led_pins[i], GPIO.HIGH)  # Set pins to high(+3.3V) to off led

p_R = GPIO.PWM(led_pins['pin_R'], freq)
p_G = GPIO.PWM(led_pins['pin_G'], freq)
p_B = GPIO.PWM(led_pins['pin_B'], freq)

p_R.start(0)      # Initial duty Cycle = 0(leds off)
p_G.start(0)
p_B.start(0)

########################
# BUTTON CONFIG
GPIO.setup(but_pins, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Button to GPIO23

########################
# CAMERA CONFIG
width = 800
height = 600

########################################################################
########################
# LED FUNCTIONS


def map(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def setColor(col):   # For example : col = 0x112233
    R_val = (col & 0x110000) >> 16
    G_val = (col & 0x001100) >> 8
    B_val = (col & 0x000011) >> 0

    R_val = map(R_val, 0, 255, 0, 100)
    G_val = map(G_val, 0, 255, 0, 100)
    B_val = map(B_val, 0, 255, 0, 100)

    p_R.ChangeDutyCycle(R_val)     # Change duty cycle
    p_G.ChangeDutyCycle(G_val)
    p_B.ChangeDutyCycle(B_val)


def setFreq(new_freq):
    p_R.ChangeFrequency(new_freq)
    p_G.ChangeFrequency(new_freq)
    p_B.ChangeFrequency(new_freq)

########################################################################
########################
# CAMERA FUNCTIONS


def decodeCam(image, cv2, pyzbar):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    barcodes = pyzbar.decode(gray)
    for barcode in barcodes:
        barcodeData = barcode.data.decode()
        barcodeType = barcode.type
        if barcodeType == "QRCODE":
            logger.debug("[ INFO ] QRCode found...")
            match = re.search(qrcode_re, barcodeData)
            if match:
                logger.debug("[ INFO ] This is a PSK Configuration QRcode...")
                return match

########################################################################
########################
# SYSTEM FUNCTIONS


def check_config():
    ssid = ""
    setColor(color_configured)
    try:
        with open(wpa_supplicant_conf, "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.replace(" ", "").startswith("ssid="):
                    ssid = line.split("=")[1].replace("\n", "")
                    logger.info(
                        "[\033[92m  OK  \033[0m] System configured to connect to {0}".format(ssid))
                    setColor(color_configured)
    except:
        pass
    finally:
        return ssid


def check_connection(ssid):
    connected = False
    result = -1
    try:
        result = subprocess.run("iwconfig | grep ESSID | grep {0}".format(ssid.replace(
            "\"", "")), shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = result.returncode
    except:
        pass
    finally:
        if result == 0:
            connected = True
            logger.info(
                "[\033[92m  OK  \033[0m] System connected to {0}".format(ssid))
            setFreq(freq)
            setColor(color_connected)
        else:
            setColor(color_configured)
            p_R.ChangeFrequency(1)
            p_G.ChangeFrequency(1)
            p_B.ChangeFrequency(1)
            logger.warning(
                '[\033[33m WARN \033[0m] System not connect to {0} yet. Retrying...'.format(ssid))
        return connected


def check_wpa_supplicant():
    try:
        p1 = subprocess.Popen(["ps", "ax"], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(["grep", "wpa_supplicant"],
                              stdin=p1.stdout, stdout=subprocess.PIPE)
        p3 = subprocess.Popen(["grep", "wlan0"], stdin=p2.stdout)
        p3.communicate()
        return p3.returncode
    except:
        logger.error(
            '[\033[31m FAIL \033[0m] Unable to check wpa_supplicant process. Please try to reboot')


def start_wpa_supplicant():
    try:
        result = subprocess.run("wpa_supplicant -B -c/etc/wpa_supplicant.conf -iwlan0 -Dnl80211,wext",
                                shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode
    except:
        logger.error(
            '[\033[31m FAIL \033[0m] Unable to start wpa_supplicant process. Please try to reboot')


def wpa_cli_reconfigure():
    try:
        result = subprocess.check_call(
            ["wpa_cli", "reconfigure"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode
    except:
        logger.error(
            '[\033[31m FAIL \033[0m] Unable to reconfigure wpa_cli. Please try to reboot')


def configuration_mode():
    setColor(color_configured_mode)
    p_R.ChangeFrequency(1)
    p_G.ChangeFrequency(1)
    p_B.ChangeFrequency(1)

    logger.info("[\033[92m  OK  \033[0m] Entering onfiguration mode")
    try:
        import cv2
        import pyzbar.pyzbar as pyzbar
        logger.info("[\033[92m  OK  \033[0m] Configuration mode loaded")
        setFreq(freq)
    except:
        logger.error(
            '[\033[31m FAIL \033[0m] Unable to load the configuraton mode. Please check all packages are installed and the camera is plugged in')

    camera = cv2.VideoCapture(0)
    camera.set(3, width)
    camera.set(4, height)

    try:
        qrcode_data = None
        led_status = False
        end_config_time = datetime.now() + timedelta(minutes=1)
        interrupt = False
        logger.debug("[ INFO ] Start reading the camera information...")
        while not qrcode_data and not interrupt and not end_config_time < datetime.now():
            # Read current frame
            button_state = GPIO.input(but_pins)
            if button_state == False:
                interrupt = True
                logger.warning(
                    '[\033[33m WARN \033[0m] Configuration mode exited by user interrupt...')
            ret, frame = camera.read()
            qrcode_data = decodeCam(frame, cv2, pyzbar)

    except:
        logger.error(
            '[\033[31m FAIL \033[0m] Unable to read the camera. Please check all packages are installed and the camera is plugged in')
    finally:
        if qrcode_data:
            ssid = qrcode_data.group(1)
            psk = qrcode_data.group(2)
            data = []
            config = ""
            if os.path.isfile(wpa_supplicant_conf):
                f = open(wpa_supplicant_conf, "r")
                lines = f.readlines()
                for line in lines:
                    if not line.startswith("network="):
                        data.append(line.replace('\n', ''))
                    else:
                        break
                f.close()
            else:
                data.append("ctrl_interface={0}".format(wpa_suppliant_ctrl))
                data.append("update_config=1")
                data.append("country={0}".format(wpa_supplicant_country))

            data.append("")
            data.append("network={")
            data.append("   ssid=\"{0}\"".format(ssid))
            data.append("   psk=\"{0}\"".format(psk))
            data.append("}")
            data.append("")
            config = "\n".join(data)
            with open(wpa_supplicant_conf, "w") as f:
                f.write(config)
                logger.info("[\033[92m  OK  \033[0m] New Wi-Fi configuration saved...")

            if check_wpa_supplicant() > 0:
                start_wpa_supplicant()
            else:
                wpa_cli_reconfigure()
        return

########################################################################
########################
# SCRIPT RUN


def main():
    ssid = ""
    sleep_time = 2
    setColor(color_started)
    time.sleep(1)
    while True:
        if GPIO.input(but_pins) == False:
            sleep_time = 2
            ssid = None
            configuration_mode()
        elif not ssid:
            sleep_time = 2
            ssid = check_config()
            if not ssid:
                logger.warning(
                    '[\033[33m WARN \033[0m] Wi-Fi not configured. Retrying...')
        else:
            sleep_time = 5
            setColor(color_connected)
            check_connection(ssid)
        time.sleep(sleep_time)

########################
# SCRIPT INIT


def start_service():
    try:
        logger.info("[\033[92m  OK  \033[0m] System started")
        main()
    except KeyboardInterrupt:
        logger.info('[\033[33m STOP \033[0m] System manually stopped ')
    except:
        logger.critical('[\033[31m FAIL \033[0m]')
    finally:
        p_R.stop()
        p_G.stop()
        p_B.stop()
        for i in led_pins:
            GPIO.output(led_pins[i], GPIO.HIGH)    # Turn off all leds
        GPIO.cleanup()


########################################################################
########################
# SCRIPT INSTALL
def _apt(package):
    try:
        subprocess.check_call(["apt-get", "install", "-y", package])
        logger.info("[\033[92m  OK  \033[0m] {0} installed".format(package))
    except:
        logger.critical(
            '[\033[31m FAIL \033[0m] Unable to install {0}'.format(package))
        exit(2)


def update_system():
    try:
        subprocess.check_call(["apt-get", "update"])
        subprocess.check_call(["apt-get", "dist-upgrade", "-y"])
        logger.info("[\033[92m  OK  \033[0m] System updated")
    except:
        logger.critical('[\033[31m FAIL \033[0m] Unable to update the system')
        exit(2)


def install_deps():
    packages = ["python3-pip", "python3-opencv", "libzbar0", "libhdf5-dev", "libhdf5-serial-dev", "libatlas-base-dev",
                "libjasper-dev", "libqtgui4", "libqt4-test"]
    for package in packages:
        _apt(package)





def install_python_packages():
    try:
        subprocess.check_call(
            ["python3", "-m", "pip", "install", "pyzbar"])
        logger.info("[\033[92m  OK  \033[0m] Python packages installed")
    except:
        logger.critical(
            '[\033[31m FAIL \033[0m] Unable to install python packages')
        exit(2)


def enable_bcm2835():
    try:
        subprocess.check_call(["modprobe", "bcm2835_v4l2"])
        logger.info("[\033[92m  OK  \033[0m] bcm2835_v4l2 enabled")
    except:
        logger.critical(
            '[\033[31m FAIL \033[0m] Unable to enable bcm2835_v4l2')
        exit(2)

def unblock_wifi():
    try:
        subprocess.check_call(["rfkill", "unblock", "wifi"])
        logger.info("[\033[92m  OK  \033[0m] rfkill removed on the Wi-Fi interface")
    except:
        logger.critical(
            '[\033[31m FAIL \033[0m] Unable to remove the rfkillon the Wi-Fi interface')
        exit(2)


def install_service():
    if not os.geteuid() == 0:
        logger.critical(
            '[\033[31m FAIL \033[0m] Please run the installation as root user')
        exit(2)
    else:
        script_path = os.path.realpath(__file__)
        try:
            data = """
[Unit]
Description=QCRODE Config
After=multi-user.target
[Service]
User=root
Type=simple
Restart=always
ExecStart=/usr/bin/python3 {0} -s
[Install]
WantedBy=multi-user.target
""".format(script_path)
            with open("/etc/systemd/system/qrcode_script.service", "w") as f:
                f.write(data)
            logger.info("[\033[92m  OK  \033[0m] Service create")
        except:
            logger.critical(
                '[\033[31m FAIL \033[0m] Unable to create the service')
            exit(2)
        try:
            subprocess.check_call(["systemctl", "enable", "qrcode_script.service"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(
                "[\033[92m  OK  \033[0m] qrcode_script.service enabled at boot")
        except:
            logger.critical(
                '[\033[31m FAIL \033[0m] Unable enable qrcode_script.service at boot')
            exit(2)
        try:
            subprocess.check_call(["systemctl", "daemon-reload"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("[\033[92m  OK  \033[0m] systemctl daemon reloaded")
        except:
            logger.critical(
                '[\033[31m FAIL \033[0m] Unable to reload systemctl')
            exit(2)
        try:
            subprocess.check_call(["systemctl", "start", "qrcode_script.service"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(
                "[\033[92m  OK  \033[0m] qrcode_script.service started")
        except:
            logger.critical(
                '[\033[31m FAIL \033[0m] Unable to start qrcode_script.service')
            exit(2)

########################################################################
########################
# SCRIPT HELP


def usage():
    print("""
written by Thomas Munzer <tmunzer[at]juniper.net>

QRCODE Configuratio script

Usage:
    -i,--install        install the script as a service
    -s,--start          start the script
    -h,--help           display this help

    """)


########################################################################
########################
# ENTRY POINT
if __name__ == "__main__":
    try:
        argv = sys.argv[1:]
        opts, args = getopt.getopt(argv, "his", ["install", "start"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    if len(opts) == 0:
        start_service()
    else:
        for opt, arg in opts:
            if opt == '-h':
                usage()
                sys.exit()
            elif opt in ("-i", "--install"):
                enable_bcm2835()
                unblock_wifi()
                update_system()
                install_deps()
                install_python_packages()
                install_service()
            elif opt in ("-s", "--start"):
                start_service()
