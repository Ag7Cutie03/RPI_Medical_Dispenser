import RPi.GPIO as GPIO
import time

class ServoController:
    def __init__(self):
        self.tray1_pin = 29  # GPIO 32 for Tray 1 (SG90)
        self.tray2_pin = 31  # GPIO 33 for Tray 2
        self.frequency = 50  # 50Hz for standard servos
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.tray1_pin, GPIO.OUT)
        GPIO.setup(self.tray2_pin, GPIO.OUT)
        self.servo1 = GPIO.PWM(self.tray1_pin, self.frequency)
        self.servo2 = GPIO.PWM(self.tray2_pin, self.frequency)
        self.servo1.start(0)
        self.servo2.start(0)
        print("ServoController initialized (real hardware)")

    def _move_servo(self, servo, angle):
        # Convert angle (0-180) to duty cycle
        duty = 2 + (angle / 18)
        servo.ChangeDutyCycle(duty)
        time.sleep(0.5)
        servo.ChangeDutyCycle(0)

    def dispense_from_tray_1(self, medicine_name):
        print(f"Dispensing from Tray 1: {medicine_name}")
        start_time = time.perf_counter()
        self._move_servo(self.servo1, 90)  # Move to 90 degrees
        time.sleep(1)
        self._move_servo(self.servo1, 0)   # Return to 0 degrees
        elapsed = time.perf_counter() - start_time
        print(f"Dispense complete (Tray 1). [BENCHMARK] Took {elapsed:.2f} seconds.")

    def dispense_from_tray_2(self, medicine_name):
        print(f"Dispensing from Tray 2: {medicine_name}")
        start_time = time.perf_counter()
        self._move_servo(self.servo2, 90)  # Move to 90 degrees
        time.sleep(1)
        self._move_servo(self.servo2, 0)   # Return to 0 degrees
        elapsed = time.perf_counter() - start_time
        print(f"Dispense complete (Tray 2). [BENCHMARK] Took {elapsed:.2f} seconds.")

    def cleanup(self):
        self.servo1.stop()
        self.servo2.stop()
        GPIO.cleanup()
        print("ServoController cleaned up.")

def get_servo_controller():
    return ServoController()

def cleanup_servo_controller(controller):
    controller.cleanup() 