# ==================================================================================================================================== # 
# Sprinkle Board Setup 
# ==================================================================================================================================== # 
# Import Microcontroller Libraries
import board
import time
import busio
import digitalio
import simpleio
from analogio import AnalogIn
import os

# Import Peripheral Libraries
import adafruit_adxl37x # High G Accelerometer | https://www.adafruit.com/product/5374
import adafruit_bno055 # 9-DOF IMU | https://www.adafruit.com/product/2472
import adafruit_ms8607 # Barometric Pressure, Humidity, and Temperature Sensor | https://www.adafruit.com/product/4716
import adafruit_rfm9x # RFM98PW-433S2 Lora Radio Module 
import adafruit_gps # GPS Module | https://www.adafruit.com/product/790
import neopixel # Fancy LED | https://www.adafruit.com/product/1655

# Define Buss Definitions
i2c = busio.I2C(board.IO9, board.IO8, frequency=48000)
spi = busio.SPI(board.IO12, MOSI=board.IO13, MISO=board.IO11)
uart = busio.UART(board.IO43, board.IO44, baudrate=9600, timeout=20)

# Define General Pin Definitions
rf_cs = digitalio.DigitalInOut(board.IO10)
rf_reset = digitalio.DigitalInOut(board.IO21)
vbatt_in = AnalogIn(board.IO14)
buzzer_pin = board.IO1
neopixel_pin = board.IO3

# Define Pyro Pin Definitions
pyro1_enable = digitalio.DigitalInOut(board.IO39)
pyro2_enable = digitalio.DigitalInOut(board.IO40)
pyro3_enable = digitalio.DigitalInOut(board.IO41)
pyro4_enable = digitalio.DigitalInOut(board.IO42)

continuity_pyro_1_pin = digitalio.DigitalInOut(board.IO7)
continuity_pyro_2_pin = digitalio.DigitalInOut(board.IO6)
continuity_pyro_3_pin = digitalio.DigitalInOut(board.IO5)
continuity_pyro_4_pin = digitalio.DigitalInOut(board.IO4)

# Define Rocket Stage and Altitudes
stage = "Booster" # Booster or Sustainer
main_deploy_altitude = 650 # Main Parachute Deployment Barometric Altitude (Feet)

cycle_type = False
# spreading_factor = 7 # Avilable Spreading Factors [6, 7, 8, 9, 10, 11, 12]
downlink_frequency = 433.0

if stage == "SprinkleMini":
    uplink_frequency = 433
    spreading_factor = 7
if stage == "Booster":
    uplink_frequency = 432
    spreading_factor = 8
if stage == "Sustainer":
    uplink_frequency = 434
    spreading_factor = 11

# ==================================================================================================================================== # 
# Establishes Variables, Rocket States, and Failure Flags
# ==================================================================================================================================== # 
# Variables
packet_number = 0
acceleration = None, None, None
gyro = None, None, None
pressure, temperature = None, None
adxl375_calibration = [0, 0, 0]
bno055_calibration = [0, 0, 0]
CALIBRATION_SAMPLES = 1000

# Rocket States
call_atribute = stage + " Aquisition of Signal Search"
event_notification = True
commisioning = False
on_pad = False
launch = False
drogue_deploy = False
main_deploy = False
touchdown = False
abort_requested = False

# Failure Flags
adxl375_flag = 0
bno055_flag = 0
ms8607_flag = 0
radio_flag = 0
gps_flag = 0
pixel_flag = 0


# ==================================================================================================================================== # 
# Peripherals Setup
# ==================================================================================================================================== #
pyro1_enable.direction = digitalio.Direction.OUTPUT
pyro2_enable.direction = digitalio.Direction.OUTPUT
pyro3_enable.direction = digitalio.Direction.OUTPUT
pyro4_enable.direction = digitalio.Direction.OUTPUT

pyro1_enable.value = False
pyro2_enable.value = False
pyro3_enable.value = False
pyro4_enable.value = False

continuity_pyro_1_pin.direction = digitalio.Direction.INPUT
continuity_pyro_2_pin.direction = digitalio.Direction.INPUT
continuity_pyro_3_pin.direction = digitalio.Direction.INPUT
continuity_pyro_4_pin.direction = digitalio.Direction.INPUT

try:    
    adxl375 = adafruit_adxl37x.ADXL375(i2c, 0x1d)  # ADXL375 IMU Initialization, Address 0x1d
except Exception as e:
    print(e)
    adxl375_flag = 1
try:    
    bno055 = adafruit_bno055.BNO055_I2C(i2c, 0x28) # BNO055 IMU Initialization, Address 0x68
except Exception as e:
    print(e)
    bno055_flag = 1
try:
    ms8607 = adafruit_ms8607.MS8607(i2c) # MS8607 Pressure Sensor Initialization, Address 0x76 pressure sensor and 0x40 humidity
    ms8607.pressure_resolution = 1 # Lower Value = Higher Sample Rate but Less Accurate
except Exception as e:
    print(e)
    ms8607_flag = 1
try:
    rfm9x = adafruit_rfm9x.RFM9x(spi, rf_cs, rf_reset, downlink_frequency)
    rfm9x.high_power = True
    rfm9x.tx_power = 23 # Higher Value = Higher Radio Output Power (Max: 23)
    rfm9x.spreading_factor = spreading_factor
except Exception as e:
    print(e)
    radio_flag = 1
try:
    gps = adafruit_gps.GPS(uart, debug=False)
except Exception as e:
    print(e)
    gps_flag = 1
try:
    pixel = neopixel.NeoPixel(neopixel_pin, 1, brightness=0.05)
    pixel[0] = (0, 255, 255)
except Exception as e:
    print(e)
    pixel_flag = 1


# ==================================================================================================================================== # 
# Check if the file exists, and if it does, increment the number in the filename
# ==================================================================================================================================== #
file_counter = 1
filename = "flight(1).csv"
files = os.listdir()

while filename in files:
    file_counter += 1
    filename = f"flight({file_counter}).csv"
print(filename)


# ==================================================================================================================================== # 
# Commmisioning + On Pad State
# ==================================================================================================================================== # 
while on_pad == False: # Remains true until AOS has been aquired and go for launch command has been sent
    time_stamp = time.monotonic()
    packet_number += 1
# ==================================================================================================================================== # 
    if adxl375_flag == 0:
        try:
            acceleration = adxl375.acceleration
        except:
            adxl375_flag = 1
    if adxl375_flag == 1 and bno055_flag == 0:
        try:
            acceleration = bno055.acceleration
        except:
            bno055_flag = 1
            acceleration = None, None, None
# ==================================================================================================================================== #
    if bno055_flag == 0:
        try:
            gyro = bno055.gyro
        except:
            bno055_flag = 1
            gyro = None, None, None
# ==================================================================================================================================== #
    if ms8607_flag == 0:
        try:
            temperature, pressure = ms8607.pressure_and_temperature
        except:
            ms8607_flag = 1
            pressure, temperature = None, None
# ==================================================================================================================================== # 
    continuity_pyro_1 = int(continuity_pyro_1_pin.value)
    continuity_pyro_2 = int(continuity_pyro_2_pin.value)
    continuity_pyro_3 = int(continuity_pyro_3_pin.value)
    continuity_pyro_4 = int(continuity_pyro_4_pin.value)
# ==================================================================================================================================== # 
    vbatt = ((vbatt_in.value * 3.5) / 65535) * 4.5
# ==================================================================================================================================== # 
    plist = (call_atribute,packet_number,time_stamp,acceleration,gyro,pressure,temperature,vbatt,"Continuity", continuity_pyro_1, continuity_pyro_2, continuity_pyro_3, continuity_pyro_4,"Flags",adxl375_flag,bno055_flag,ms8607_flag,radio_flag,gps_flag,pixel_flag,"KO6FTH")
    print(plist)
    try:
        rfm9x.send(bytes(str(plist), "utf-8"))
    except:
        radio_flag = 1
    simpleio.tone(buzzer_pin, 500, 0.1)

    if commisioning == False:
        try:
            rfm9x.frequency_mhz = uplink_frequency
            packet = rfm9x.receive(timeout=5.0)
            rfm9x.frequency_mhz = downlink_frequency
        except KeyboardInterrupt:
            exit()
        except:
            rfm9x.frequency_mhz = downlink_frequency
            radio_flag = 1 
        if packet is not None:
            try:
                packet_text = packet.decode('ascii')
            except:
                packet_text = "Decode Function Issue"
            
            if packet_text == stage + " AOS": # Checks Received Packet and Compares Custom Phrase to Confirm Radio Functionality
                try:
                    pixel[0] = (255, 255, 255)
                except:
                    pixel_flag = 1
                call_atribute = stage + " Aquisition of Signal Confirmed"
                print(call_atribute)
                commisioning = True        

            else: 
                failed_attempt = (stage + " Failed Attempt: " + packet_text)
                print(failed_attempt)
                try:
                    rfm9x.send(bytes(str(failed_attempt), "utf-8"))
                except:
                    radio_flag = 1


    if commisioning == True:
        try:
            rfm9x.frequency_mhz = uplink_frequency
            packet = rfm9x.receive(timeout=5.0)
            rfm9x.frequency_mhz = downlink_frequency
        except KeyboardInterrupt:
            exit()
        except:
            rfm9x.frequency_mhz = downlink_frequency
            radio_flag = 1 
        if packet is not None:
            try:
                packet_text = packet.decode('ascii')
            except:
                packet_text = "Decode Function Issue"

            if packet_text == stage + " Calibrate": # Checks Received Packet and Compares Custom Phrase to Calibrate Sensors
                print(stage + " Calibration Initialized")
                try:
                    rfm9x.send(bytes(str(stage + " Calibration Initialized"), "utf-8"))
                except:
                    radio_flag = 1
                try:
                    pixel[0] = (255, 0, 0)
                except:
                    pixel_flag = 1

                # Samples Data for Calibration
                try:
                    for i in range(CALIBRATION_SAMPLES):
                        adxl375_acceleration = adxl375.acceleration
                        adxl375_calibration[0] += adxl375_acceleration[0]
                        adxl375_calibration[1] += adxl375_acceleration[1]
                        adxl375_calibration[2] += adxl375_acceleration[2]
                        time.sleep(0.01)
                except Exception as e:
                    print(e)
                    adxl375_flag = 1
                try:
                    for i in range(CALIBRATION_SAMPLES):
                        bno055_acceleration = bno055.acceleration
                        bno055_calibration[0] += bno055_acceleration[0]
                        bno055_calibration[1] += bno055_acceleration[1]
                        bno055_calibration[2] += bno055_acceleration[2]
                        time.sleep(0.01)
                except Exception as e:
                    print(e)
                    bno055_flag = 1

                # Calculate average Calibration Values
                adxl375_calibration = [x / CALIBRATION_SAMPLES for x in adxl375_calibration]
                bno055_calibration = [x / CALIBRATION_SAMPLES for x in bno055_calibration]

                # Indication of Calibration Completion 
                print(stage + " Calibration Completed")
                try:
                    rfm9x.send(bytes(str(stage + " Calibration Completed"), "utf-8"))
                except:
                    radio_flag = 1
                try:
                    pixel[0] = (255, 255, 255)
                except:
                    pixel_flag = 1

            if packet_text == stage + " Pyro": # Checks Received Packet and Compares Custom Phrase to Fire Pyros
                print(stage + " Pyro Mode")
                try:
                    rfm9x.send(bytes(str(stage + " Pyro Mode"), "utf-8"))
                except:
                    radio_flag = 1
                while True:
                    try:
                        pixel[0] = (0, 255, 0)
                    except:
                        pixel_flag = 1
                    simpleio.tone(buzzer_pin, 500, 0.1)
                    try:
                        rfm9x.frequency_mhz = uplink_frequency
                        packet = rfm9x.receive(timeout=5.0)
                        rfm9x.frequency_mhz = downlink_frequency
                    except KeyboardInterrupt:
                            exit()
                    except:
                        rfm9x.frequency_mhz = downlink_frequency
                        radio_flag = 1 
                    if packet is not None:
                        try:
                            packet_text = packet.decode('ascii')
                        except:
                            packet_text = "Decode Function Issue"
                    if packet_text in ("Pyro_1", "pyro_1", "Pyro 1", "pyro 1", "p1"): 
                        try:
                            pixel[0] = (255, 0, 0)
                        except:
                            pixel_flag = 1
                        simpleio.tone(buzzer_pin, 500, 0.1)
                        pyro1_enable.value = True
                        time.sleep(1)
                        pyro1_enable.value = False
                        print(stage + " Pyro 1 Fired")
                        try:
                            rfm9x.send(bytes(str(stage + " Pyro 1 Fired"), "utf-8"))
                        except:
                            radio_flag = 1
                    elif packet_text in ("Pyro_2", "pyro_2", "Pyro 2", "pyro 2", "p2"): 
                        try:
                            pixel[0] = (255, 0, 0)
                        except:
                            pixel_flag = 1
                        simpleio.tone(buzzer_pin, 500, 0.1)
                        pyro2_enable.value = True
                        time.sleep(1)
                        pyro2_enable.value = False
                        print(stage + " Pyro 2 Fired")
                        try:
                            rfm9x.send(bytes(str(stage + " Pyro 2 Fired"), "utf-8"))
                        except:
                            radio_flag = 1
                    elif packet_text in ("Pyro_3", "pyro_3", "Pyro 3", "pyro 3", "p3"): 
                        try:
                            pixel[0] = (255, 0, 0)
                        except:
                            pixel_flag = 1
                        simpleio.tone(buzzer_pin, 500, 0.1)
                        pyro3_enable.value = True
                        time.sleep(1)
                        pyro3_enable.value = False
                        print(stage + " Pyro 3 Fired")
                        try:
                            rfm9x.send(bytes(str(stage + " Pyro 3 Fired"), "utf-8"))
                        except:
                            radio_flag = 1
                    elif packet_text in ("Pyro_4", "pyro_4", "Pyro 4", "pyro 4", "p4"): 
                        try:
                            pixel[0] = (255, 0, 0)
                        except:
                            pixel_flag = 1
                        simpleio.tone(buzzer_pin, 500, 0.1)
                        pyro4_enable.value = True
                        time.sleep(1)
                        pyro4_enable.value = False
                        print(stage + " Pyro 4 Fired")
                        try:
                            rfm9x.send(bytes(str(stage + " Pyro 4 Fired"), "utf-8"))
                        except:
                            radio_flag = 1
                    elif packet_text in ("Exit", "exit"): 
                        try:
                            pixel[0] = (255, 255, 255)
                        except:
                            pixel_flag = 1
                        break
                    else:
                        try:
                            print(stage + " Wrong Response: " + packet_text)
                            time.sleep(1)
                            rfm9x.send(bytes(str(stage + " Wrong Response: " + packet_text), "utf-8"))
                        except:
                            radio_flag = 1

            if packet_text == stage + " Launch": # Checks Received Packet and Compares Custom Phrase to Confirm Go for Launch
                try:
                    pixel[0] = (0, 255, 0)
                except:
                    pixel_flag = 1
                on_pad = True    
            
            elif packet_text not in (stage + " Calibrate", stage + " Pyro", stage + "Launch", "Exit", "exit"): 
                failed_attempt = (stage + " Failed Attempt: " + packet_text)
                print(failed_attempt)
                try:
                    rfm9x.send(bytes(str(failed_attempt), "utf-8"))
                except:
                    radio_flag = 1           


# ==================================================================================================================================== # 
# Indication of Launch
# ==================================================================================================================================== #
call_atribute = stage + " Armed for Launch"
print(call_atribute)
packet_number = 0
ground_altitude = (1- (pressure/1013.25)**0.190284 ) * 145366.45


# ==================================================================================================================================== # 
# Rocket Flight
# ==================================================================================================================================== # 
with open(filename, "w") as file:
    row = f"{stage}\n"
    file.write(row)
    file.write("adxl375_calibration_x,adxl375_calibration_y,adxl375_calibration_z,bno055_calibration_x,bno055_calibration_y,bno055_calibration_z\n")
    row = f"{adxl375_calibration[0]},{adxl375_calibration[1]},{adxl375_calibration[2]},{bno055_calibration[0]},{bno055_calibration[1]},{bno055_calibration[2]}\n"
    file.write(row)
    file.write("packet_number,time_stamp,pressure,temperature,vbatt,continuity_pyro_1,continuity_pyro_2,continuity_pyro_3,continuity_pyro_4,commisioning,on_pad,launch,drogue_deploy,main_deploy,touchdown,adxl375_flag,bno055_flag,ms8607_flag,radio_flag,gps_flag,pixel_flag\n")
    start_time = time.monotonic()
    
    while (time.monotonic() - start_time) < 42: # Remains True Until Timer has Concluded   
        time_stamp = time.monotonic()
        packet_number += 1
        packet_text = None # ALSO PART OF ABORT CODE
# ==================================================================================================================================== # 
 
        try:    # NEW ABORT CODE: listens for packets after launch triggered
            rfm9x.frequency_mhz = uplink_frequency
            packet = rfm9x.receive(timeout = 0.05)
            rfm9x.frequency_mhz = downlink_frequency
        except:
            packet = None

        if packet is not None:
            try:
                packet_text = packet.decode('ascii')
            except:
                packet_text = "Decode Function Issue"

        if packet_text == stage + " Abort": # NEW ABORT CODE HERE, only able to activate after launch command sent
            pixel[0] = (128, 0, 128)
            abort_requested = True

            call_atribute = stage + " Abort Received"
            print(call_atribute)
            try:
                    rfm9x.send(bytes(call_atribute, "utf-8"))
            except:
                radio_flag = 1

        if abort_requested: # NEW ABORT CODE - Stops writing to csv file so it can be closed
            call_atribute = stage + " Abort - Flight Terminated"
            print(call_atribute)
            try:
                rfm9x.send(bytes(call_atribute, "utf-8"))
            except:
                radio_flag = 1
            event_notification = True
            pyro1_enable.value = False
            pyro2_enable.value = False
            pyro3_enable.value = False
            pyro4_enable.value = False
            break
# ==================================================================================================================================== #   
        if adxl375_flag == 0:
            try:
                acceleration = adxl375.acceleration
            except:
                adxl375_flag = 1
        if adxl375_flag == 1 and bno055_flag == 0:
            try:
                acceleration = bno055.acceleration
            except:
                bno055_flag = 1
                acceleration = None, None, None
# ==================================================================================================================================== #
        if bno055_flag == 0:
            try:
                gyro = bno055.gyro
            except:
                bno055_flag = 1
                gyro = None, None, None
# ==================================================================================================================================== #
        if ms8607_flag == 0:
            try:
                temperature, pressure = ms8607.pressure_and_temperature
            except:
                ms8607_flag = 1
                pressure, temperature = None, None
# ==================================================================================================================================== # 
        continuity_pyro_1 = int(continuity_pyro_1_pin.value)
        continuity_pyro_2 = int(continuity_pyro_2_pin.value)
        continuity_pyro_3 = int(continuity_pyro_3_pin.value)
        continuity_pyro_4 = int(continuity_pyro_4_pin.value)
# ==================================================================================================================================== # 
        vbatt = ((vbatt_in.value * 3.5) / 65535) * 4.5
# ==================================================================================================================================== #  

        if launch == False:
            altitude = (1- (pressure/1013.25)**0.190284 ) * 145366.45
            if altitude >= (ground_altitude+100):
                call_atribute = stage + " Launch Detected"
                launch = True
                event_notification = True

        if launch == True and drogue_deploy == False:
            call_atribute = stage + " Drogue Deployed"
            drogue_deploy = True
            event_notification = True
            drogue_deploy_time = time.monotonic()

        if drogue_deploy == True and main_deploy == False and (time.monotonic() - drogue_deploy_time) >= 3:
            altitude = (1- (pressure/1013.25)**0.190284 ) * 145366.45
            if altitude <= main_deploy_altitude:
                call_atribute = stage + " Main Deployed"
                main_deploy = True
                event_notification = True

        if main_deploy == True and touchdown == False:
            touchdown = True
            event_notification = True

        row = f"{packet_number},{time_stamp},{pressure},{temperature},{vbatt},{continuity_pyro_1},{continuity_pyro_2},{continuity_pyro_3},{continuity_pyro_4},{commisioning},{on_pad},{launch},{drogue_deploy},{main_deploy},{touchdown},{adxl375_flag},{bno055_flag},{ms8607_flag},{radio_flag},{gps_flag},{pixel_flag}\n"
        file.write(row)
        
        if event_notification == True:
            plist = (call_atribute,packet_number,time_stamp,acceleration,gyro,pressure,temperature,vbatt,"Continuity", continuity_pyro_1, continuity_pyro_2, continuity_pyro_3, continuity_pyro_4,"Flags",adxl375_flag,bno055_flag,ms8607_flag,radio_flag,gps_flag,pixel_flag,"KO6FTH")
            try:
                rfm9x.send(bytes(str(plist), "utf-8"))
            except:
                radio_flag = 1
            event_notification = False

# ==================================================================================================================================== # 
# Deletes csv file if flight aborted
# ==================================================================================================================================== #
if abort_requested and not launch:
    if filename in os.listdir():
        os.remove(filename)

# ==================================================================================================================================== # 
# Displays the Prints per Second
# ==================================================================================================================================== #
    pps = packet_number / (time.monotonic() - start_time)
    print("Max prints per second: {:.2f}".format(pps))

# ==================================================================================================================================== # 
# GPS Recovery
# ==================================================================================================================================== # 
try:
    gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0") # Specifies what Data the GPS Sends Over UART
    gps.send_command(b"PMTK220,2000") # Specifies the Rate at Which GPS Data is Sent
except:
    gps_flag = 1

last_print = time.monotonic()
while True:
    try:
        gps.update()
        current = time.monotonic()
        if current - last_print >= 2.5:
            last_print = current
            if not gps.has_fix:
                message = stage
                message += "\nWaiting for fix..."
                continue
        
            # We have a fix! (gps.has_fix is true)
            message = stage
            message += "\nFix timestamp: {}/{}/{} {:02}:{:02}:{:02}\n".format(
                        gps.timestamp_utc.tm_hour,  # not get all data like year, day,
                        gps.timestamp_utc.tm_min,  # month!
                        gps.timestamp_utc.tm_sec,
                    )
            message += "Latitude: {0:.6f} degrees\n".format(gps.latitude)
            message += "Longitude: {0:.6f} degrees\n".format(gps.longitude)
            if gps.altitude_m is not None:
                message += "Altitude: {} meters\n".format(gps.altitude_m)
        try:
            rfm9x.send(bytes(str(message), "utf-8"))
            if cycle_type == True:
                spreading_factor += 1
                if spreading_factor >= 13:
                    spreading_factor = 7
                rfm9x.spreading_factor = spreading_factor 
        except:
            radio_flag = 1
    except KeyboardInterrupt:
            exit()
    except Exception as e:
        print(e)
        gps_flag = 1
        try:
            rfm9x.send(bytes(str("GPS Issue"), "utf-8"))
        except:
            radio_flag = 1
