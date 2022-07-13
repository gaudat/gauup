### Controlling the motor through HTTP

Endpoint: `http://{ip}/?value={value}`

#### Drill motor

Set value to 4915 to stop the motor.\
Set value between 4916 and 6553 to spin the motor.\
Larger value makes the motor quicker.

Set value between 3277 and 4914 to spin the motor in reverse.\
Smaller value makes the motor reverse quicker.

The motor stops after 2 seconds if no commands are received.

#### Servo motor

Set value between 2457 and 8000 to rotate the servo motor.\
4915 corresponds to the midpoint.\
Test with small increments to prevent the motor from stalling.

The servo motor will stop giving torque after 2 seconds when no commands are received.

2500 corresponds to the door opened at 90 degrees. \
6400 corresponds to the door shut. \
4915 corresponds to the middle point at 45 degrees open.

### Setting up WiFi SSID and password

1. Ensure the lithium ion battery is disconnected.
2. Connect a cable to the USB-C port on the black circuit board.
3. Connect the other end of the cable to a PC.
4. Wait for a serial port to show up on the PC. You may need to install drivers for the CH340 USB-UART manually.
5. Connect to the serial port with miniterm/Putty/TeraTerm. 115200, 8N1.
6. Press "EN" button next to the usb connector on the black circuit board. This is the reset button.
7. Press enter in the terminal when it prompts you to enter config mode. If you missed the 5 second time frame, press "EN" to reset.
8. Type `s <ssid>` then press enter. Replace with your real WiFi SSID.
9. Type `p <password>` then press enter. Replace with your real WiFi password.
10. Type `s` and then enter. Verify the SSID is correct.
11. Type `p` and then enter. Verify the password is correct.
12. Type `r` and then enter to reset the board.
13. Look at the terminal and check the board's IP address after connecting to the WiFi network.

### The blue LED light

On boot the blue LED light should blink rapidly for a few seconds. This is the time frame where config mode can be entered.

Next the blue LED light should blink slowly for a few times. This is the board attempting to connect to the configured WiFi network.

After that the blue LED should light up dimly. It is actually a low duty cycle PWM. This is the control signal to the motor driver.

After a few seconds of calibrating the motor driver the web server will go up. From now on the motor can be controlled through HTTP.

