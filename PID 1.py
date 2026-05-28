from machine import Pin, PWM
import time
from hcsr04 import HCSR04
from time import ticks_ms, ticks_diff


sensor = HCSR04(trigger_pin=19, echo_pin = 18, echotimeout_us = 10000)


IN1 = PWM(Pin(5), freq=1000)
IN2 = PWM(Pin(17), freq=1000)


IN3 = PWM(Pin(16), freq=1000)
IN4 = PWM(Pin(4), freq=1000)
MAX_DUTY = 65535

def set_motor(pin_forward, pin_reverse, speed):
    speed = max(min(speed, 100), -100) 
    duty = int(abs(speed) * MAX_DUTY / 100) 

    if speed > 0:
        pin_forward.duty_u16(duty)
        pin_reverse.duty_u16(0)

    elif speed < 0:
        pin_forward.duty_u16(0)
        pin_reverse.duty_u16(duty)

    else:
        pin_forward.duty_u16(0)
        pin_reverse.duty_u16(0)

def motorA(speed):
    set_motor(IN1, IN2, speed)

def motorB(speed):
    set_motor(IN3, IN4, speed)
        
        
class PIDController:
    def __init__(self, Kp, Ki, Kd, setpoint):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.previous_error = 0
        self.integral = 0

    def compute (self, process_variable, dt):
        
        error = process_variable - self.setpoint

        P_out = self.Kp * error
    
        self.integral += error * dt 
        I_out = self.Ki * self.integral
    
        
        derivative = (error - self.previous_error) /dt
        D_out = self.Kd * derivative
    
        
        output = P_out + I_out + D_out
    
        
        self.previous_error = error
    
        return output

setpoint = 60.0  
last_time = ticks_ms()

pid = PIDController (1.0, 0, 0.1, setpoint) 


while True:
    current_time = ticks_ms()
    dt = ticks_diff(current_time, last_time) / 1000
    last_time = current_time

    if dt <= 0:
        dt = 0.01

    process_variable = sensor.distance_cm()

    motor_speed = pid.compute(process_variable, dt)

    motor_speed = max(min(motor_speed, 100), -100)

    motorA(motor_speed)
    motorB(motor_speed)

    time.sleep(0.05)
   
    
