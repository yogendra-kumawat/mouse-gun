# 🎯 Gyroscope Gun Controller — Physical FPS Mouse

<div align="center">

**Point a real gun-shaped controller to aim. Pull a trigger to shoot. No mouse needed.**

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)]()
[![STM32](https://img.shields.io/badge/STM32-03234B?style=for-the-badge&logo=stmicroelectronics&logoColor=white)]()
[![MPU6050](https://img.shields.io/badge/MPU6050-IMU-yellow?style=for-the-badge)]()
[![Bluetooth](https://img.shields.io/badge/Bluetooth-Serial-blue?style=for-the-badge&logo=bluetooth)]()

</div>

> **Works with any PC game that uses a mouse** — Counter-Strike, Valorant, or any FPS. The physical gun replaces the mouse entirely: tilting/rotating the gun moves the crosshair, and pulling the trigger clicks.

---

## 🧭 Table of Contents

- [How It Works](#-how-it-works)
- [System Architecture](#-system-architecture)
- [Hardware](#-hardware)
- [Firmware Deep Dive — main.c](#-firmware-deep-dive--mainc)
- [Python Controller — main.ipynb](#-python-controller--mainipynb)
- [Gyro → Mouse Math](#-gyro--mouse-math)
- [Serial Data Format](#-serial-data-format)
- [Setup & Installation](#-setup--installation)
- [Tuning Parameters](#-tuning-parameters)
- [Known Issues & Roadmap](#-known-issues--roadmap)

---

## 💡 How It Works

```
Physical Gun                      PC
────────────────                  ──────────────────────────
Tilt gun left/right   ──────────► Mouse moves left/right
Tilt gun up/down      ──────────► Mouse moves up/down
Pull trigger          ──────────► Left mouse click (shoot)
```

The gun has an **MPU6050 IMU** (gyroscope + accelerometer) mounted inside. An **STM32** reads sensor data at high speed and streams it wirelessly over **Bluetooth** to a Python script running on the PC. Python translates the gyroscope angular velocities into mouse movements using `pyautogui`, and fires a click when the trigger button is pressed.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────┐
│          Physical Gun               │
│                                     │
│  MPU6050 IMU                        │
│  (I²C @ 100 kHz)                   │
│       │                             │
│       ▼                             │
│  STM32F103                          │
│  Read Accel + Gyro (14 bytes)       │
│  Read trigger button (PA0)          │
│  Format → ASCII serial string       │
│  Transmit → USART1 @ 230,400 baud  │
│       │                             │
│  Bluetooth Module (HC-05 or similar)│
└───────┼─────────────────────────────┘
        │ Wireless serial (/dev/rfcomm1)
        ▼
┌─────────────────────────────────────┐
│       Python — main.ipynb           │
│                                     │
│  Read line from serial              │
│  Parse Accel XYZ + Gyro XYZ        │
│  Average over N=200 samples         │
│  Compute Δgyro (diff from prev)     │
│  Noise gate → filter jitter         │
│  pyautogui.move(Gy, Gz)            │
│  If trigger → pyautogui.click()    │
└─────────────────────────────────────┘
        │
        ▼
  🎮 FPS Game (CS2, Valorant, etc.)
```

---

## 🔩 Hardware

| Component | Purpose |
|-----------|---------|
| STM32F103 ("Blue Pill") | Reads IMU, handles serial TX |
| MPU6050 (GY-521 module) | 6-axis IMU — gyro + accelerometer |
| HC-05 Bluetooth module | Wireless serial bridge to PC |
| Push button (trigger) | Connected to PA0 — fires mouse click |
| Gun-shaped enclosure | Holds all components |
| 3.7V LiPo battery | Portable power |

### Wiring

| STM32 Pin | Connected To | Notes |
|-----------|-------------|-------|
| PB6 (I2C1_SCL) | MPU6050 SCL | I²C clock |
| PB7 (I2C1_SDA) | MPU6050 SDA | I²C data |
| PA9 (USART1_TX) | HC-05 RX | Serial to Bluetooth |
| PA10 (USART1_RX) | HC-05 TX | Serial from Bluetooth |
| PA0 | Trigger button (pull to GND) | Active LOW input |
| 3.3V | MPU6050 VCC | |
| GND | MPU6050 GND, button GND | Common ground |

> ⚠️ **Power note:** The HC-05 operates at 3.3V logic but needs 5V VCC. Use the STM32's 5V pin (from USB) for HC-05 power, and a voltage divider on the HC-05 RX line to protect it from 5V signals.

---

## 🛠️ Firmware Deep Dive — `main.c`

### MPU6050 Initialization

Wakes the sensor from sleep mode by writing `0` to the Power Management register:

```c
void MPU6050_Init(void) {
    uint8_t check, Data;
    // Read WHO_AM_I register (0x75) — should return 0x68 (104 decimal)
    HAL_I2C_Mem_Read(&hi2c1, MPU6050_ADDR, 0x75, 1, &check, 1, 1000);

    if (check == 104) {
        Data = 0; // Write 0 to PWR_MGMT_1 → wake up sensor
        HAL_I2C_Mem_Write(&hi2c1, MPU6050_ADDR, 0x6B, 1, &Data, 1, 1000);
    }
}
```

### Reading All Sensor Data in One Burst (14 bytes)

The MPU6050 register map is contiguous — one I²C read from `0x3B` gets all 14 bytes (Accel X/Y/Z + Temperature + Gyro X/Y/Z):

```c
void MPU6050_Read_All(void) {
    uint8_t Rec_Data[14];
    HAL_I2C_Mem_Read(&hi2c1, MPU6050_ADDR, 0x3B, 1, Rec_Data, 14, 1000);

    // Bytes 0–5: Accelerometer X, Y, Z
    Accel_X_RAW = (int16_t)(Rec_Data[0] << 8 | Rec_Data[1]);
    Accel_Y_RAW = (int16_t)(Rec_Data[2] << 8 | Rec_Data[3]);
    Accel_Z_RAW = (int16_t)(Rec_Data[4] << 8 | Rec_Data[5]);

    // Bytes 6–7: Temperature (skipped — not used)

    // Bytes 8–13: Gyroscope X, Y, Z
    Gyro_X_RAW  = (int16_t)(Rec_Data[8]  << 8 | Rec_Data[9]);
    Gyro_Y_RAW  = (int16_t)(Rec_Data[10] << 8 | Rec_Data[11]);
    Gyro_Z_RAW  = (int16_t)(Rec_Data[12] << 8 | Rec_Data[13]);
}
```

### Main Loop — Non-blocking UART TX

Uses **interrupt-driven transmission** (`HAL_UART_Transmit_IT`) so the sensor reading loop never stalls waiting for the serial port to clear:

```c
volatile uint8_t uart_tx_ready = 1;  // flag: 1 = free to send

while (1) {
    MPU6050_Read_All();

    // Read trigger button (active LOW — PA0 pulled to GND when pressed)
    if (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_0) == GPIO_PIN_RESET)
        press = 1;

    if (uart_tx_ready == 1) {
        uart_tx_ready = 0;  // lock immediately

        uart_buf_len = sprintf(uart_buf,
            "Press:%d | A_X:%d A_Y:%d A_Z:%d | G_X:%d G_Y:%d G_Z:%d\r\n",
            press,
            Accel_X_RAW, Accel_Y_RAW, Accel_Z_RAW,
            Gyro_X_RAW,  Gyro_Y_RAW,  Gyro_Z_RAW);

        HAL_UART_Transmit_IT(&huart1, (uint8_t *)uart_buf, uart_buf_len);
        press = 0;  // reset trigger after sending
    }
}

// Callback: called when TX completes → unlock for next send
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART1)
        uart_tx_ready = 1;
}
```

### I²C & UART Configuration

| Peripheral | Setting | Value |
|------------|---------|-------|
| I2C1 | Clock speed | 100 kHz (standard mode) |
| I2C1 | Addressing | 7-bit |
| MPU6050 I²C address | Shifted for HAL | `0x68 << 1 = 0xD0` |
| USART1 | Baud rate | **230,400** |
| USART1 | Word length | 8-bit, no parity |
| System clock | Source | HSI (8 MHz, no PLL) |

---

## 🐍 Python Controller — `main.ipynb`

### Configuration

```python
PORT         = '/dev/rfcomm1'   # Bluetooth serial port
                                # Windows: 'COM5' (check Device Manager)
BAUD_RATE    = 230400

noise_margin = 700    # minimum gyro delta to register as intentional motion
sensitivity  = 80     # divide gyro value by this → mouse pixel movement
my_count     = 200    # number of samples to average per update
```

### Main Loop Logic

```python
while True:
    if ser.in_waiting > 0:
        raw_line = ser.readline()
        data = raw_line.decode('utf-8', errors='ignore').strip()

        # Accumulate N=200 samples and average them
        while count:
            count -= 1
            pairs      = data.split('|')
            click      = int(pairs[0].split(':')[1])    # trigger state
            accel_*    = parse accel XYZ from pairs[1]
            gyro_*     = parse gyro XYZ from pairs[2]

        count = my_count

        # Average gyro over N samples
        g_y = g_y / count
        g_z = g_z / count

        # Compute change from previous frame
        diff_gy = pre_gy - g_y
        diff_gz = pre_gz - g_z
        pre_gy, pre_gz = g_y, g_z

        # Noise gate — ignore micro-jitter below threshold
        if abs(diff_gz) > noise_margin or abs(diff_gy) > noise_margin:
            pyautogui.move(g_y / sensitivity, 0)   # left/right aim
            pyautogui.move(0, g_z / sensitivity)   # up/down aim
            if click == 1:
                pyautogui.click()                   # fire
```

---

## 📐 Gyro → Mouse Math

### Which Axes Do What

The MPU6050 is mounted inside the gun. The axes map to gun motion as follows:

| MPU6050 Axis | Physical Motion | Mouse Action |
|-------------|----------------|--------------|
| **Gyro Y** (`G_Y`) | Gun swings left / right (yaw) | Mouse X (horizontal aim) |
| **Gyro Z** (`G_Z`) | Gun tilts up / down (pitch) | Mouse Y (vertical aim) |
| **Gyro X** (`G_X`) | Gun rolls (twist) | Not used |

### Noise Gating

Raw gyro values at rest are never perfectly zero — they contain noise (typically ±200–500 LSB). The `noise_margin = 700` threshold ignores any delta below that, preventing crosshair drift when the gun is held still:

```
|Δgyro| < 700  →  no mouse movement  (gun is still)
|Δgyro| ≥ 700  →  move mouse         (intentional aim)
```

### Sensitivity Formula

```
mouse_pixels = gyro_value / sensitivity
```

With `sensitivity = 80` and a typical gyro swing of ~8000 LSB:
```
8000 / 80 = 100 pixels per swing
```

Decrease `sensitivity` to move faster (more pixels per swing). Increase it to slow down.

### Averaging (Anti-Jitter)

Instead of reacting to every single noisy sample, the script **accumulates 200 samples** then averages them before computing the delta. This acts as a low-pass filter — sudden noise spikes are averaged out, smooth intentional motion is preserved.

---

## 📡 Serial Data Format

Every packet from the STM32 is a human-readable ASCII line:

```
Press:0 | A_X:12088 A_Y:-6412 A_Z:9832 | G_X:-430 G_Y:747 G_Z:-89\r\n
│         │                               │
│         Accelerometer (raw 16-bit)      Gyroscope (raw 16-bit, ±250°/s range)
│
Trigger (0=not pressed, 1=pressed)
```

**Raw value scale:**
- At default ±250°/s gyro range: `1 LSB = 1/131 degrees/sec`
- A fast 90° sweep takes ~0.1s → angular rate ~900°/s → raw value ~`900 × 131 = 117,900 LSB`

---

## 🚀 Setup & Installation

### Python Dependencies

```bash
pip install pyautogui pyserial
```

### Pair the Bluetooth Module (Linux)

```bash
# Scan and pair HC-05
bluetoothctl
  scan on
  pair XX:XX:XX:XX:XX:XX   # your HC-05 MAC address
  trust XX:XX:XX:XX:XX:XX
  exit

# Bind to rfcomm
sudo rfcomm bind 1 XX:XX:XX:XX:XX:XX
# Now accessible at /dev/rfcomm1
```

### Pair the Bluetooth Module (Windows)

1. Add HC-05 in Bluetooth settings → pair with PIN `1234`
2. Check Device Manager → Ports (COM & LPT) for the assigned COM port
3. Set `PORT = 'COM5'` (or whichever port appears)

### Flash the Firmware

1. Open `main.c` in **STM32CubeIDE**
2. Connect STM32 via ST-Link programmer
3. Build and flash

### Run

```bash
jupyter notebook main.ipynb
```

Run cells top to bottom. Keep the gun connected and start the game — the crosshair will follow your gun.

---

## 🎛️ Tuning Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| `sensitivity` | `80` | Lower = faster aim, Higher = slower |
| `noise_margin` | `700` | Lower = more responsive but drifty, Higher = more stable |
| `my_count` | `200` | Lower = faster reaction, Higher = smoother (more averaging) |
| Gyro full-scale range | `±250°/s` (default) | Change in MPU6050 config reg `0x1B` for faster guns |

### Quick Tuning Guide

- **Crosshair drifts when gun is still** → increase `noise_margin`
- **Aim feels sluggish / too slow** → decrease `sensitivity`
- **Aim feels jittery** → increase `my_count` (more averaging)
- **Aim feels delayed** → decrease `my_count`

---

## 📁 Project Structure

```
mouse-gun/
├── firmware/
│   └── main.c           # STM32 firmware (I²C IMU + UART TX)
├── python/
│   └── main.ipynb       # PC-side: serial parse + mouse control
└── README.md
```

---

## ⚠️ Known Issues & Roadmap

### Current Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Crosshair drifts slowly | Gyro bias / temperature drift | Calibrate gyro bias on startup; subtract offset |
| `OSError: [Errno 5]` on Linux | Bluetooth rfcomm disconnected mid-session | Reconnect and re-bind rfcomm; auto-reconnect in Python |
| Averaging loop blocks on same line | `readline()` only reads new data once | Fix: collect N consecutive lines, not re-parse the same one |

### Roadmap

- [ ] **Gyro bias calibration** — average 1000 samples at startup with gun held still; subtract as offset
- [ ] **Complementary filter** — blend gyro + accelerometer for absolute orientation (eliminates drift entirely)
- [ ] **Recoil effect** — pulse a vibration motor on trigger press for haptic feedback
- [ ] **More buttons** — reload (R key), ADS (right-click), crouch — mapped to additional GPIO buttons
- [ ] **USB HID mode** — present the STM32 as a USB HID mouse directly, eliminating Python entirely for lower latency
- [ ] **Windows Bluetooth fix** — test and document COM port setup for Windows users

---

*Built with ❤️ using STM32 HAL, MPU6050, and PyAutoGUI.*
