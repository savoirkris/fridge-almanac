"""讀機器的序列埠紀錄。用法：python tools_serial_log.py [秒數] [--reset] [--out 檔案]"""
import re, sys, time, serial
argv = sys.argv[1:]
secs = int(next((a for a in argv if a.isdigit()), 30))
out = open(argv[argv.index("--out") + 1], "w") if "--out" in argv else sys.stdout
s = serial.Serial()
s.port = "/dev/cu.usbserial-1430"; s.baudrate = 115200; s.timeout = 0.5
s.dtr = False; s.rts = False
s.open()
if "--reset" in argv:               # 拉 RTS 重開機（不進下載模式）
    s.rts = True; time.sleep(0.2); s.rts = False
end = time.time() + secs
while time.time() < end:
    chunk = s.read(4096)
    if chunk:
        out.write(re.sub(rb"\x1b\[[0-9;]*m", b"", chunk).decode("utf-8", "replace"))
        out.flush()
