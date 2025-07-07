from rpi_servo import get_servo_controller, cleanup_servo_controller
import time

if __name__ == "__main__":
    print("Starting servo debug test...")
    controller = get_servo_controller()
    try:
        print("Resetting both Tray 1 and Tray 2 to 0 at start")
        controller._move_servo(controller.servo1, 0)
        controller._move_servo(controller.servo2, 0)
        time.sleep(2)
        print("Both trays set to 0 at start.")
        print("Moving Tray 1 to 130")
        controller._move_servo(controller.servo1, 0)
        print("Tray 1 angle test complete.")

        print("Moving Tray 2 to 130")
        controller._move_servo(controller.servo2, 0)
        print("Tray 2 angle test complete.")
    finally:
        print("Resetting both Tray 1 and Tray 2 to 0")
        controller._move_servo(controller.servo1, 0)
        controller._move_servo(controller.servo2, 0)
        print("Both trays set to 0.") 