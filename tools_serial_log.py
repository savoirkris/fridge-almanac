"""讀機器的序列埠紀錄。用法：python tools_serial_log.py [秒數] [--reset]"""
import sys, time, serial
secs = int(next((a for a in sys.argv[1:] if a.isdigit()), 30))
s = serial.Serial()
s.port = "/dev/cu.usbserial-1430"; s.baudrate = 115200; s.timeout = 0.5
s.dtr = False; s.rts = False
s.open()
if "--reset" in sys.argv:           # 拉 RTS 重開機（不進下載模式）
    s.rts = True; time.sleep(0.2); s.rts = False
end = time.time() + secs
buf = b""
while time.time() < end:
    buf += s.read(4096)
import re
text = re.sub(rb"\x1b\[[0-9;]*m", b"", buf).decode("utf-8", "replace")
print(text)
