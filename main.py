import pyautogui
import serial
pyautogui.PAUSE = 0
pyautogui.FAILSAFE=False
PORT = 'COM6' 
BAUD_RATE = 9600
ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
screen_width, screen_height = pyautogui.size()
next_val=0
pre_gy=0
pre_gz=0
my_count=200
count=my_count
noise_margin=700
sensitivity=80
while True:
    a_x = 0
    a_y = 0
    a_z = 0
    g_x =0
    g_y =0
    g_z =0
    if ser.in_waiting > 0:
        raw_line = ser.readline()
        data = raw_line.decode('utf-8', errors='ignore').strip()
        try:
            while (count):
                count=count-1
                pairs = data.split('|')
                accel_words = pairs[1].split()
                gyor_words=pairs[2].split()
                click=int(pairs[0].split(':')[1])
                a_x = a_x+int(accel_words[0].split(':')[1].strip())
                a_y = a_y+int(accel_words[1].split(':')[1].strip())
                a_z = a_z+int(accel_words[2].split(':')[1].strip())
                g_x =g_x+ int(gyor_words[0].split(':')[1].strip())
                g_y = g_y+int(gyor_words[1].split(':')[1].strip())
                g_z = g_z+int(gyor_words[2].split(':')[1].strip())
        except:
            continue  
        count=my_count  
        g_y=g_y/count
        g_z=g_z/count    
        diff_gy=pre_gy-g_y
        diff_gz=pre_gz-g_z
 
        pre_gy=g_y
        pre_gz=g_z
        current_x, current_y = pyautogui.position()
        # if (16>a_x/count/100>15):
        #     pyautogui.moveTo(current_x,screen_height / 2)
        # print(a_x/count/100,a_y/count/100,a_z/count/100)
        
        if (abs(diff_gz)>noise_margin or abs(diff_gy)>noise_margin):
            print("hiiiaia")
            pyautogui.move(g_y/sensitivity, 0)
            pyautogui.move(0,g_z/sensitivity)
           
            if (click==1):
                pyautogui.click()    
    