import os, gc, time
from libs.PlatTasks import DetectionApp
from libs.PipeLine import PipeLine
from libs.Utils import *
from ybUtils.YbUart import YbUart
from libs.YbProtocol import YbProtocol

# ===================== 硬件初始化 =====================
uart = YbUart(baudrate=115200)
pto = YbProtocol()

# ===================== 基础配置 =====================
display_mode = "lcd"
rgb888p_size = [640, 480]
root_path = "/sdcard/mp_deployment_source/"

# ===================== 🟢 融合方案B的终极优化参数 =====================
CONFIDENCE_THRESHOLD = 0.40              # 置信度阈值
PEST_APPEAR_CONFIRM_FRAMES = 3            # 害虫出现：连续3帧确认
PEST_DISAPPEAR_CONFIRM_FRAMES = 10        # 害虫消失：连续10帧确认
MIN_SEND_INTERVAL_MS = 800                 # 🟢 新增：最小发送间隔（800ms），避免短时间内频繁发送

def main():
    # ===================== 🟢 融合方案B的状态变量（分离确认和发送）=====================
    last_confirmed_status = "NONE_DETECTED" # 最终确认的稳定状态
    temp_candidate_pest = "NONE_DETECTED"   # 候选害虫（正在确认中）
    appear_count = 0                         # 候选害虫连续出现帧数
    disappear_count = 0                      # 连续未检测到已锁定害虫的帧数

    last_sent_status = "NONE_DETECTED"      # 🟢 新增：已经发送过的状态（避免重复发送）
    last_send_time = 0                       # 🟢 新增：上次发送的时间戳

    try:
        # ===================== 初始化AI和Pipeline =====================
        deploy_conf = read_json(root_path + "/deploy_config.json")
        kmodel_path = root_path + deploy_conf["kmodel_path"]
        labels = deploy_conf["categories"]
        model_conf = deploy_conf["confidence_threshold"]
        nms_threshold = deploy_conf["nms_threshold"]
        model_input_size = deploy_conf["img_size"]
        model_type = deploy_conf["model_type"]
        anchors = []
        if model_type == "AnchorBaseDet":
            anchors = deploy_conf["anchors"][0] + deploy_conf["anchors"][1] + deploy_conf["anchors"][2]

        pl = PipeLine(rgb888p_size=rgb888p_size, display_mode=display_mode)
        pl.create()
        display_size = pl.get_display_size()

        det_app = DetectionApp(
            "video", kmodel_path, labels, model_input_size, anchors, model_type,
            model_conf, nms_threshold,
            rgb888p_size, display_size, debug_mode=0
        )
        det_app.config_preprocess()

        print("✅ 融合方案B优化版害虫检测系统启动成功！")
        print(f"⚙️ 参数：置信度{CONFIDENCE_THRESHOLD} | 出现确认{PEST_APPEAR_CONFIRM_FRAMES}帧 | 消失确认{PEST_DISAPPEAR_CONFIRM_FRAMES}帧 | 最小发送间隔{MIN_SEND_INTERVAL_MS}ms")
        print(f"📤 串口策略：状态确认+间隔达标才发送，绝不跳变刷屏")

        # ===================== 主循环 =====================
        while True:
            img = pl.get_frame()
            res = det_app.run(img)
            det_app.draw_result(pl.osd_img, res)

            # ===================== 🟢 1. 解析当前帧结果 =====================
            current_frame_pest = "NONE_DETECTED"
            max_conf = 0
            if res and isinstance(res, dict) and len(res.get("scores", [])) > 0:
                for i in range(len(res["scores"])):
                    score = res["scores"][i]
                    if score > max_conf and score >= CONFIDENCE_THRESHOLD:
                        max_conf = score
                        current_frame_pest = labels[int(res["idx"][i])]

            # ===================== 🟢 2. 状态确认逻辑（先确认状态，不发送）=====================
            # 情况A：当前已锁定某种害虫
            if last_confirmed_status != "NONE_DETECTED":
                if current_frame_pest == last_confirmed_status:
                    disappear_count = 0 # 重置消失计数
                else:
                    disappear_count += 1
                    # 连续足够多帧没检测到，才更新确认状态
                    if disappear_count >= PEST_DISAPPEAR_CONFIRM_FRAMES:
                        last_confirmed_status = "NONE_DETECTED"
                        disappear_count = 0
                        print(f"✅ 状态确认: {last_confirmed_status} (目标消失)")

            # 情况B：当前状态是NONE，正在寻找新目标
            else:
                if current_frame_pest != "NONE_DETECTED":
                    if current_frame_pest == temp_candidate_pest:
                        appear_count += 1
                        # 连续确认帧数达标，更新确认状态
                        if appear_count >= PEST_APPEAR_CONFIRM_FRAMES:
                            last_confirmed_status = current_frame_pest
                            temp_candidate_pest = "NONE_DETECTED"
                            appear_count = 0
                            print(f"✅ 状态确认: {last_confirmed_status} (置信度:{max_conf:.2f})")
                    else:
                        temp_candidate_pest = current_frame_pest
                        appear_count = 1
                else:
                    temp_candidate_pest = "NONE_DETECTED"
                    appear_count = 0

            # ===================== 发送逻辑（完全解耦，仅在状态变化+间隔达标时发送）=====================
            current_time = time.ticks_ms()
            # 两个条件同时满足才发送：
            # 1. 确认状态和已发送状态不同 2. 满足最小发送间隔
            if (last_confirmed_status != last_sent_status
                and time.ticks_diff(current_time, last_send_time) >= MIN_SEND_INTERVAL_MS):

                # 发送状态，加换行符
                uart.send(last_confirmed_status + "\n")
                uart.send( "HEALTHY"+ "\n")
                # 更新发送记录
                last_sent_status = last_confirmed_status
                last_send_time = current_time
                print(f"📤 串口发送: {last_sent_status}")

            # 4. 刷新屏幕
            pl.show_image()
            gc.collect()

    except KeyboardInterrupt as e:
        print("用户中断: ", e)
    except Exception as e:
        print(f"运行错误: {e}")
        import sys
        sys.print_exception(e)
    finally:
        if 'pl' in locals():
            pl.destroy()
        # 退出时复位
        if last_sent_status != "NONE_DETECTED":
            uart.send("NONE_DETECTED\n")
        print("程序已安全退出")

if __name__ == "__main__":
    main()
