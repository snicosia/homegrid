import xbee
import time
from machine import I2C, Pin

ON_STATE = 0
OFF_STATE = 1

STATE = ON_STATE

coordinator_mac_addr64 = None

red_pin = Pin("D2", mode=Pin.OUT, value=0)
blue_pin = Pin("D4", mode=Pin.OUT, value=0)
green_pin = Pin("D3", mode=Pin.OUT, value=0)
relay_pin = Pin("D12", mode=Pin.OUT, value=1)  # 1 Relay on, 0 Relay off
button_pin = Pin("D10", mode=Pin.IN, pull=Pin.PULL_DOWN)


def button_handler(state, time_tracker):
    next_state = state

    if time_tracker.is_button_debounce_timer_expired() and button_pin.value():
        time_tracker.set_button_debounce_timer()
        if state == ON_STATE:
            next_state = OFF_STATE
        elif state == OFF_STATE:
            next_state = ON_STATE
        print("Button Pressed")

    return next_state


def i2c_init():
    i2c = I2C(1, freq=400000)  # create I2C peripheral at frequency of 400kHz


def discover_coordinator(coordinator_mac_addr64, time_tracker):
    mac_addr64 = coordinator_mac_addr64
    if time_tracker.is_discover_coordinator_timer_expired() and mac_addr64 == None:
        time_tracker.set_discover_coordinator_timer()
        try:
            xbee_discover_list = xbee.discover()

            for device in xbee_discover_list:
                if "coordinator" == device["node_id"]:
                    mac_addr64 = device["sender_eui64"]
                    print("Coordinator discovered: {}".format(mac_addr64))
        except Exception as e:
            print("Discover Failure: {}".format(str(e)))

    return mac_addr64


def get_sensor_payload():
    return "Sensor Payload"


def transmit_sensor_payload(state, coordinator_mac_addr64, time_tracker):
    if (
        time_tracker.is_transmit_sensor_payload_timer_expired()
        and coordinator_mac_addr64
    ):
        time_tracker.set_transmit_sensor_payload_timer()
        sensor_payload = None
        sensor_payload = get_sensor_payload()
        if sensor_payload:
            try:
                xbee.transmit(
                    coordinator_mac_addr64, "{},{}".format(state, sensor_payload)
                )
            except Exception as e:
                print("Transmission failure: {}".format(str(e)))


def periodic_run(state, coordinator_mac_addr64, time_tracker):
    if state == ON_STATE:
        red_pin.value(0)
        blue_pin.value(0)
        green_pin.value(0)
        relay_pin.value(1)
    elif state == OFF_STATE:
        red_pin.value(1)
        blue_pin.value(0)
        green_pin.value(0)
        relay_pin.value(0)

    transmit_sensor_payload(state, coordinator_mac_addr64, time_tracker)


def command_message_receiver_handler(state):
    next_state = state

    received_msg = xbee.receive()
    if received_msg:
        # Get the sender's 64-bit address and payload from the received message.
        sender_mac_addr = "".join(
            "{:02x}".format(x) for x in received_msg["sender_eui64"]
        )
        payload = received_msg["payload"].decode()
        print("Data received from {}: {}".format(sender_mac_addr, payload))

        if payload == "on":
            next_state = ON_STATE
        elif payload == "off":
            next_state = OFF_STATE

    return next_state


i2c_init()


def is_timer_expired(current_time_ms, previous_time_ms, timeout):
    return (current_time_ms - previous_time_ms) > timeout


class TimeTracker:
    def __init__(self):
        self.current_time_ms = 0

        self.discover_coordinator_timer_ms = 0
        self.transmit_sensor_payload_timer_ms = 0
        self.button_debounce_timer_ms = 0

        self.discover_coordinator_timeout_ms = 10000
        self.transmit_sensor_payload_timeout_ms = 1000
        self.button_debounce_timeout_ms = 1000

    def set_current_time_ms(self):
        self.current_time_ms = time.ticks_ms()

    def set_discover_coordinator_timer(self):
        self.discover_coordinator_timer_ms = time.ticks_ms()

    def set_transmit_sensor_payload_timer(self):
        self.transmit_sensor_payload_timer_ms = time.ticks_ms()

    def set_button_debounce_timer(self):
        self.button_debounce_timer_ms = time.ticks_ms()

    def is_discover_coordinator_timer_expired(self):
        return is_timer_expired(
            self.current_time_ms,
            self.discover_coordinator_timer_ms,
            self.discover_coordinator_timeout_ms,
        )

    def is_transmit_sensor_payload_timer_expired(self):
        return is_timer_expired(
            self.current_time_ms,
            self.transmit_sensor_payload_timer_ms,
            self.transmit_sensor_payload_timeout_ms,
        )

    def is_button_debounce_timer_expired(self):
        return is_timer_expired(
            self.current_time_ms,
            self.button_debounce_timer_ms,
            self.button_debounce_timeout_ms,
        )


time_tracker = TimeTracker()

while True:
    time_tracker.set_current_time_ms()
    coordinator_mac_addr64 = discover_coordinator(coordinator_mac_addr64, time_tracker)
    periodic_run(STATE, coordinator_mac_addr64, time_tracker)
    STATE = command_message_receiver_handler(STATE)
    STATE = button_handler(STATE, time_tracker)
