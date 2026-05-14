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

# ===================== 🟢 终极优化参数（完全匹配你的数据）=====================
CONFIDENCE_THRESHOLD = 0.40          # 置信度阈值，适配你0.4左右的模型
PEST_APPEAR_CONFIRM_FRAMES = 3        # 害虫出现：连续3帧检测到才确认（避免误检）
PEST_DISAPPEAR_CONFIRM_FRAMES = 10    # 害虫消失：连续10帧没检测到才切NONE（超强防抖，解决跳变）
LOCK_ON_SAME_PEST = True               # 锁定同一种害虫：中间偶尔检测到其他害虫不切换

def main():
    # ===================== 终极防抖状态变量 =====================
    final_sent_status = "NONE_DETECTED" # 最终发送的状态（只有这个会发串口）
    temp_candidate_pest = "NONE_DETECTED" # 候选害虫（正在确认中）
    locked_pest_type = "NONE_DETECTED"    # 已锁定的害虫类型
    # 分开计数
    appear_count = 0    # 候选害虫连续出现帧数
    disappear_count = 0 # 连续未检测到已锁定害虫的帧数

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

        print("✅ 终极优化版害虫检测系统启动成功！")
        print(f"⚙️ 参数：置信度{CONFIDENCE_THRESHOLD} | 出现确认{PEST_APPEAR_CONFIRM_FRAMES}帧 | 消失确认{PEST_DISAPPEAR_CONFIRM_FRAMES}帧")
        print(f"📤 串口策略：仅在状态变化时发送，绝不刷屏")

        # ===================== 主循环 =====================
        while True:
            img = pl.get_frame()
            res = det_app.run(img)
            det_app.draw_result(pl.osd_img, res)

            # ===================== 🟢 终极核心逻辑 =====================
            # 1. 解析当前帧结果
            current_frame_pest = "NONE_DETECTED"
            max_conf = 0
            if res and isinstance(res, dict) and len(res.get("scores", [])) > 0:
                for i in range(len(res["scores"])):
                    score = res["scores"][i]
                    if score > max_conf and score >= CONFIDENCE_THRESHOLD:
                        max_conf = score
                        current_frame_pest = labels[int(res["idx"][i])]

            # -------------------------- 2. 状态机逻辑 --------------------------
            # 情况A：当前已锁定某种害虫（final_sent_status != NONE）
            if final_sent_status != "NONE_DETECTED":
                # 子情况A1：当前帧又检测到了已锁定的害虫
                if current_frame_pest == final_sent_status:
                    disappear_count = 0 # 重置消失计数
                # 子情况A2：当前帧没检测到，或者检测到了其他害虫
                else:
                    disappear_count += 1
                    # 只有连续足够多帧都没检测到已锁定害虫，才切NONE
                    if disappear_count >= PEST_DISAPPEAR_CONFIRM_FRAMES:
                        final_sent_status = "NONE_DETECTED"
                        locked_pest_type = "NONE_DETECTED"
                        disappear_count = 0
                        # 🟢 只在状态变化时发送！
                        uart.send(final_sent_status + "\n")
                        print(f"📤 状态变更: {final_sent_status} (目标消失)")

            # 情况B：当前状态是NONE_DETECTED，正在寻找新目标
            else:
                # 子情况B1：当前帧检测到了害虫
                if current_frame_pest != "NONE_DETECTED":
                    # 和候选害虫一致
                    if current_frame_pest == temp_candidate_pest:
                        appear_count += 1
                        # 连续确认帧数达标，锁定目标
                        if appear_count >= PEST_APPEAR_CONFIRM_FRAMES:
                            final_sent_status = current_frame_pest
                            locked_pest_type = current_frame_pest
                            temp_candidate_pest = "NONE_DETECTED"
                            appear_count = 0
                            # 🟢 只在状态变化时发送！
                            uart.send(final_sent_status + "\n")
                            print(f"📤 状态变更: {final_sent_status} (置信度:{max_conf:.2f})")
                    # 检测到新的候选害虫
                    else:
                        temp_candidate_pest = current_frame_pest
                        appear_count = 1
                # 子情况B2：当前帧没检测到害虫
                else:
                    temp_candidate_pest = "NONE_DETECTED"
                    appear_count = 0

            # 3. 刷新屏幕
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
        if final_sent_status != "NONE_DETECTED":
            uart.send("NONE_DETECTED\n")
        print("程序已安全退出")

if __name__ == "__main__":
    main()