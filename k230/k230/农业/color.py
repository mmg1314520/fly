import time, os, sys, gc
from media.sensor import *
from media.display import *
from media.media import *
from libs.YbProtocol import YbProtocol
from ybUtils.YbUart import YbUart
from ybUtils.YbRGB import YbRGB

# ===================== 硬件初始化 =====================
uart = YbUart(baudrate=115200) # 硬件UART引脚发送
pto = YbProtocol()
rgb = YbRGB()

# ===================== 配置参数 =====================
DISPLAY_WIDTH = 640
DISPLAY_HEIGHT = 480

# 颜色阈值 (建议先用IDE阈值编辑器重新校准)
COLOR_THRESHOLDS = [
    (56, 100, -12, 1, 27, 80),  # 0: 枯黄色
    (30, 48, -30, -10, 8, 30),   # 1: 绿色
]
DRAW_COLORS = [(255, 255, 0), (0, 255, 0)]
COLOR_LABELS = ['WITHERED_YELLOW', 'GREEN']

# 🟢 稳定化参数（优化后）
STABLE_FRAMES = 3                # 连续3帧检测到同一状态才确认
MIN_SEND_INTERVAL_MS = 1000      # 最小发送间隔：1000毫秒（1秒）
BLOB_AREA_THRESHOLD = 800        # 面积阈值：过滤小噪点

def init_sensor():
    sensor = Sensor()
    sensor.reset()
    sensor.set_framesize(width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
    sensor.set_pixformat(Sensor.RGB565)
    return sensor

def init_display():
    Display.init(Display.ST7701, to_ide=True)
    MediaManager.init()

def process_blobs(img, threshold_idx):
    """返回检测到的总面积"""
    blobs = img.find_blobs([COLOR_THRESHOLDS[threshold_idx]], area_threshold=BLOB_AREA_THRESHOLD, merge=True)
    total_area = 0

    if blobs:
        for blob in blobs:
            img.draw_rectangle(blob[0:4], thickness=4, color=DRAW_COLORS[threshold_idx])
            img.draw_cross(blob[5], blob[6], thickness=2)
            total_area += blob[4]

    return total_area

def main():
    # ===================== 状态变量（修正后）=====================
    last_confirmed_status = "NONE"  # 最终确认的状态
    temp_status = "NONE"            # 临时状态
    temp_status_count = 0           # 临时状态持续帧数
    last_send_time = 0              # 上次发送时间（毫秒）
    last_sent_status = "NONE"       # 已经发送过的状态（避免重复发送）

    try:
        sensor = init_sensor()
        init_display()
        sensor.run()
        clock = time.clock()

        print("程序启动成功！稳定化枯萎识别模式已开启...")

        while True:
            clock.tick()
            img = sensor.snapshot()

            # -------------------------- 1. 颜色识别 --------------------------
            y_area = process_blobs(img, 0)
            g_area = process_blobs(img, 1)

            # -------------------------- 2. 初步判定 --------------------------
            current_raw_status = "NONE"
            if g_area > 0:
                ratio = y_area / g_area
                if ratio >= 0.20:
                    current_raw_status = "WITHERED"
                else:
                    current_raw_status = "HEALTHY"

            # -------------------------- 3. 状态稳定化逻辑 --------------------------
            if current_raw_status == temp_status:
                temp_status_count += 1
            else:
                temp_status = current_raw_status
                temp_status_count = 1

            # 连续足够帧数，更新最终确认状态
            if temp_status_count >= STABLE_FRAMES:
                last_confirmed_status = temp_status

            # -------------------------- 4. 发送逻辑（--------------------------
            current_time = time.ticks_ms()
            # 两个条件同时满足才发送：
            # 1. 和上次发送的状态不同 2. 满足最小发送间隔
            if (last_confirmed_status != last_sent_status
                and time.ticks_diff(current_time, last_send_time) >= MIN_SEND_INTERVAL_MS):

                # 发送状态，加换行符方便上位机解析
                uart.send(last_confirmed_status + "\n")
                uart.send( "NONE_DETECTED"+ "\n")
                # 控制RGB灯
                if last_confirmed_status == "WITHERED":
                    rgb.show_rgb((255, 255, 0))
                elif last_confirmed_status == "HEALTHY":
                    rgb.show_rgb((0, 255, 0))
                else:
                    rgb.show_rgb((0, 0, 0))

                # 更新发送记录
                last_sent_status = last_confirmed_status
                last_send_time = current_time
                print(f"✅ 状态确认: {last_confirmed_status} | 📤 已发送到硬件串口")

            # -------------------------- 5. 显示 --------------------------
            Display.show_image(img)
            gc.collect()

    except KeyboardInterrupt as e:
        print("用户中断: ", e)
    except Exception as e:
        print(f"发生错误: {e}")
        import sys
        sys.print_exception(e)
    finally:
        if 'sensor' in locals() and isinstance(sensor, Sensor):
            sensor.stop()
        Display.deinit()
        MediaManager.deinit()
        rgb.show_rgb((0, 0, 0))
        print("程序已安全退出")

if __name__ == "__main__":
    main()
