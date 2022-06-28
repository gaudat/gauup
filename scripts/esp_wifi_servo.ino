#include <WiFi.h>
#include <EEPROM.h>
#include <esp32-hal-ledc.h>

// Constants
static const uint16_t server_port = 80;
static const char default_wifi_name[] = "TOP TEXT";
static const char default_wifi_pass[] = "BOTTOM TEXT";
static const int default_servo_pos = 4915;

// Global state
char wifi_name[128];
char wifi_pass[128];
bool shell_line_complete = false;
char line_buf[256];
static const size_t char_limit = (sizeof(line_buf) / sizeof(char));
size_t line_buf_length = 0;
uint32_t config_deadline;
bool config_deadline_active = false;
int servo_pos = 4915; // 4915.2 == 1500 us
uint32_t last_web_command = 0;
uint32_t web_timeout = 2000;

WiFiServer server(server_port);                   // Server will be at port 80

void shell_handle(char input_char) {
  // Handle one character received from shell
  if (input_char == '\r') {
    shell_line_complete = true;
    return;
  } else if (input_char == 8) {
    if (line_buf_length >= 1) {
      // Empty line just in case
      Serial.print('\r');
      for (size_t i = 0; i < line_buf_length; i++) {
        Serial.print(' ');
      }
      // Then update the buffer
      line_buf[--line_buf_length] = 0;

    }
    return;
  } else if (!(input_char >= 0x20 && input_char <= 0x7e)) {
    // Ignore out of range
    return;
  }
  // Else copy the line in
  // line_buf_length is position of the next character to add
  line_buf[line_buf_length++] = input_char;
  if (line_buf_length >= char_limit) {
    // Overflow
    line_buf[char_limit - 1] = 0;
    Serial.println("Overflow");
  } else {
    line_buf[line_buf_length] = 0;
  }
}

void shell_ssid() {
  if (strlen(line_buf) <= 2) {
    // Print only
    Serial.println("WiFi SSID: ");
    Serial.println(wifi_name);
    return;
  }
  if (line_buf[1] != ' ') {
    Serial.println("Get SSID: s");
    Serial.println("Set SSID: s <wifi_ssid>");
    return;
  }
  strncpy(wifi_name, line_buf + 2, sizeof(wifi_name));
  make_config();
  return;
}


void shell_password() {
  if (strlen(line_buf) <= 2) {
    // Print only
    Serial.println("WiFi password: ");
    Serial.println(wifi_pass);
    return;
  }
  if (line_buf[1] != ' ') {
    Serial.println("Get password: p");
    Serial.println("Set password: p <wifi_pass>");
    return;
  }
  strncpy(wifi_pass, line_buf + 2, sizeof(wifi_pass));
  make_config();
  return;
}

void shell_reset() {
  Serial.println("Resetting");
  ESP.restart();
}

void shell_parse() {
  // Parse the line saved in global line buffer
  Serial.print("\r\n");
  if (line_buf_length == 0) {
    // Do nothing and return
    Serial.println("Available commands: (s)sid, (p)assword, (r)eset");
    return;
  }
  switch (line_buf[0]) {
    case 's':
      shell_ssid();
      break;
    case 'p':
      shell_password();
      break;
    case 'r':
      shell_reset();
      break;
    default:
      Serial.println("Unknown command");
      Serial.println("Available commands: (s)sid, (p)assword, (r)eset");
      break;
  }
  return;
}

void shell_loop() {
  if (!Serial.available()) return;
  if (config_deadline_active) {
    Serial.println("Entered config mode.");
    config_deadline_active = false;
  }
  char input_char = Serial.read();
  shell_handle(input_char);
  Serial.print('\r');
  Serial.print(line_buf);
  if (shell_line_complete) {
    shell_parse();
    // Clean up shell line
    line_buf_length = 0;
    memset(line_buf, 0, sizeof(line_buf));
    shell_line_complete = false;
  }
}

void make_config() {
  size_t addr = 0;
  addr += EEPROM.writeByte(addr, 0xcc);
  addr += EEPROM.writeByte(addr, 's');
  addr += EEPROM.writeUInt(addr, (uint32_t) strlen(wifi_name));
  addr += EEPROM.writeBytes(addr, wifi_name, strlen(wifi_name));
  addr += EEPROM.writeByte(addr, 'p');
  addr += EEPROM.writeUInt(addr, (uint32_t) strlen(wifi_pass));
  addr += EEPROM.writeBytes(addr, wifi_pass, strlen(wifi_pass));
  Serial.print("Saved config. Size: ");
  Serial.println(addr);
  EEPROM.commit();
}

bool read_config() {
  uint8_t magic = EEPROM.readByte(0);
  if (magic == 0xcc) {
    Serial.println("Reading saved config");
  } else {
    return false;
  }
  magic = EEPROM.readByte(1);
  if (magic != 's') {
    Serial.println("Failed to read saved SSID");
    return false;
  }
  uint32_t read_length = EEPROM.readUInt(2);
  EEPROM.readBytes(2 + sizeof(uint32_t), wifi_name, read_length);
  size_t addr = read_length + 2 + sizeof(uint32_t);
  magic = EEPROM.readByte(addr);
  if (magic != 'p') {
    Serial.println("Failed to read saved password");
    return false;
  }
  addr += 1;
  read_length = EEPROM.readUInt(addr);
  addr += sizeof(uint32_t);
  EEPROM.readBytes(addr, wifi_pass, read_length);
  return true;
}

void connect_wifi() {
  WiFi.begin(wifi_name, wifi_pass);       // Connecting to the wifi network

  char cycle[] = "-/|\\";
  size_t cycle_length = strlen(cycle);
  size_t cycle_i = 0;

  while (WiFi.status() != WL_CONNECTED)   // Waiting for the responce of wifi network
  {
    digitalWrite(2, !digitalRead(2));
    delay(500);
    Serial.print("\rConnecting to WiFi ");
    Serial.print(cycle[cycle_i]);
    cycle_i ++;
    cycle_i %= cycle_length;
  }
  Serial.println("");
  Serial.println("Connection Successful");
}

void setup() {
  // put your setup code here, to run once:

  // Initialize string arrays
  memset(wifi_name, 0, sizeof(wifi_name));
  memset(wifi_pass, 0, sizeof(wifi_pass));
  memset(line_buf, 0, sizeof(line_buf));

  Serial.begin(115200);

  // LED
  pinMode(2, OUTPUT);

  // Read config from eeprom
  EEPROM.begin(256);
  if (!read_config()) {
    // Set up default config
    Serial.println("Using default config");
    strncpy(wifi_name, default_wifi_name, sizeof(wifi_name));
    strncpy(wifi_pass, default_wifi_pass, sizeof(wifi_pass));
    make_config();
  }
  Serial.println("\r\nWiFi SSID: ");
  Serial.println(wifi_name);
  Serial.println("\r\nWiFi password: ");
  Serial.println(wifi_pass);
  config_deadline = millis() + 5000;
  config_deadline_active = true;
  Serial.println("\r\nSwitching to operational mode in 5 seconds.");
  Serial.println("Press enter now to enter config mode.");

  // Rapid blink
  uint32_t blink_interval = 100;
  uint32_t last_blink = millis();
  digitalWrite(2, HIGH);
  while ((!config_deadline_active) || (millis() <= config_deadline)) {
    shell_loop();
    if (config_deadline_active && millis() > last_blink + blink_interval) {
      digitalWrite(2, !digitalRead(2));
      last_blink = millis();
    } else if (!config_deadline_active) {
      digitalWrite(2, LOW);
    }
  }
  if (config_deadline_active && millis() > config_deadline) {
    Serial.println("Entering operational mode.");
  }

  connect_wifi();
  digitalWrite(2, LOW);

  Serial.println("\r\nIP address: ");
  Serial.println(WiFi.localIP());         // Getting the IP address


  ledcSetup(1, 50, 16); // channel 1, 50 Hz, 16-bit width
  ledcAttachPin(2, 1);
  ledcWrite(1, default_servo_pos); // Moved the servo to 90 degree

  Serial.print("\r\nCalibrating motor controller ... ");
  delay(5000);
  Serial.println("Done");

  Serial.print("Starting server ... ");
  server.begin();                          // Starting the server
  Serial.println("Done");
}

void loop()
{
  if ((millis() - last_web_command) > web_timeout) {
    // This check runs when no client is connected
    // Switch off the motor
    if (ledcRead(1) != default_servo_pos) {
      Serial.println("Disconnected timeout");
      ledcWrite(1, default_servo_pos);
    }
  }
  WiFiClient client = server.available();   //Checking if any client request is available or not
  if (client)
  {
    char buffer[256];
    memset(buffer, 0, sizeof(buffer));
    size_t buffer_ptr = 0;
    while (client.connected()) {
      if ((millis() - last_web_command) > web_timeout) {
        // This check runs when a client is connected
        // Switch off the motor
        if (ledcRead(1) != default_servo_pos) {
          Serial.println("Connected timeout");
          ledcWrite(1, default_servo_pos);
        }
      }
      if (client.available()) {           // if there is some client data available
        char c = client.read();
        if (c == '\n') {
          // Ignore newline
          continue;
        }
        buffer[buffer_ptr++] = c;
        if (buffer_ptr >= sizeof(buffer)) {
          // Prevent overflow
          buffer_ptr = sizeof(buffer) - 1;
        }
        if (c == '\r') {
          // Line is complete
          Serial.println(buffer);

          if (strncmp(buffer, "GET ", 4) != 0) {
              // This is not the request line
              Serial.println("Not request line");
              continue;
          }

          if (strncmp(buffer, "GET / ", 6) == 0) {
            Serial.println("Get root");
            // Print readme
            client.println("HTTP/1.1 200 OK");
            client.println("Content-Type: text/plain");
            client.println();
            client.print("Endpoint: http://");
            client.print(WiFi.localIP());
            client.println("/?value=<value>");
            client.println();
            client.println("Set value to 4915 to stop the motor.");
            client.println("Set value between 4916 and 6553 to spin the motor.");
            client.println("Larger value makes the motor quicker.");
            client.println();
            client.println("Set value between 3277 and 4914 to spin the motor in reverse.");
            client.println("Smaller value makes the motor reverse quicker.");
            client.println();
            client.println("The motor stops after 2 seconds if no commands are received.");
            break;      // break out of the while loop:
          }

          if (strstr(buffer, "/?value=") != NULL) {
            Serial.println("Has value");
            int new_value = 0;
            int count = sscanf(buffer, "GET /?value=%d", &new_value);

            if (count < 1 || new_value < 3277 || new_value > 6553) {
              client.println("HTTP/1.1 400 Bad Request");
              client.println("Content-Type: text/plain");
              client.println();
              if (count < 1) {
                client.println("<value> cannot be parsed.");
              } else {
                client.println("Supplied <value> is out of range.");
              }
              break;
            }
            servo_pos = new_value;
            Serial.print("Set output to ");
            Serial.println(servo_pos);
            client.println("HTTP/1.1 200 OK");
            client.println("Content-Type: text/plain");
            client.println();
            client.print("Set output to ");
            client.println(servo_pos);
            ledcWrite(1, servo_pos);
            last_web_command = millis();
            break;
          }

          Serial.println("Get 404");
          client.println("HTTP/1.1 404 Not Found");
          client.println("Content-Type: text/plain");
          client.println();
          client.print("Go to http://");
          client.print(WiFi.localIP());
          client.println(" for instructions.");
          break;
        
        }
      }
    }
    client.stop();
  }
}
