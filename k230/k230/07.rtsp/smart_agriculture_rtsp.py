import network
import time
import gc
import uctypes
import os
import ujson
import sys
import socket

import ulab.numpy as np
import multimedia as mm
from media.vencoder import *
from media.sensor import *
from media.media import *
from media.display import *
from libs.PlatTasks import DetectionApp


WIFI_SSID = "A203_WIFI"
WIFI_PASSWORD = "a203a203"

# Keep the session name aligned with the Qt side default URL:
# rtsp://K230_IP:8554/face
SESSION_NAME = "face"
RTSP_PORT = 8554

STREAM_WIDTH = 512
STREAM_HEIGHT = 288
STREAM_FPS = 5
STREAM_BITRATE = 100
AI_WIDTH = 1920
AI_HEIGHT = 1080

PEST_ROOT_PATH = "/sdcard/mp_deployment_source"
PEST_CONFIDENCE_THRESHOLD = 0.20
DEBUG_PRINT_INTERVAL = 25
STATUS_PORT = 9000
STATUS_SEND_INTERVAL = 20

WITHER_CHECK_INTERVAL = 15
WITHER_STABLE_FRAMES = 3
WITHER_MIN_GREEN_PIXELS = 1200
WITHER_MIN_PLANT_PIXELS = 4000
WITHER_MIN_YELLOW_PIXELS = 6000
WITHER_RATIO_THRESHOLD = 0.35
PLANT_BOX_SAMPLE_STEP = 8


def align_up(x, align):
    return ((x + align - 1) // align) * align


def connect_wifi(ssid, password):
    sta = network.WLAN(0)
    if sta.isconnected():
        return sta

    sta.connect(ssid, password)
    while sta.ifconfig()[0] == "0.0.0.0":
        time.sleep(1)

    return sta


class SimpleRtspServer:
    def __init__(self):
        self.rtspserver = mm.rtsp_server()
        self.venc_chn = VENC_CHN_ID_0
        self.running = False
        self.det_app = None
        self.labels = []
        self.last_pest_name = "NONE_DETECTED"
        self.last_wither_name = "NONE"
        self.frame_count = 0
        self.wither_temp_status = "NONE"
        self.wither_temp_count = 0
        self.wither_confirmed_status = "NONE"
        self.last_plant_box = None
        self.last_sent_pest = ""
        self.last_sent_wither = ""
        self.status_socket = None

    def start(self):
        width = align_up(STREAM_WIDTH, 16)
        height = STREAM_HEIGHT
        ai_width = align_up(AI_WIDTH, 16)

        self.sensor = Sensor()
        self.sensor.reset()
        self.sensor.set_framesize(width=width, height=height, alignment=12, chn=CAM_CHN_ID_0)
        self.sensor.set_pixformat(Sensor.YUV420SP, chn=CAM_CHN_ID_0)
        self.sensor.set_framesize(width=ai_width, height=AI_HEIGHT, chn=CAM_CHN_ID_1)
        self.sensor.set_pixformat(PIXEL_FORMAT_RGB_888_PLANAR, chn=CAM_CHN_ID_1)

        self.encoder = Encoder()
        self.encoder.SetOutBufs(self.venc_chn, 8, width, height)

        Display.init(Display.ST7701, width=640, height=480, to_ide=True)
        MediaManager.init()

        chn_attr = ChnAttrStr(
            self.encoder.PAYLOAD_TYPE_H264,
            self.encoder.H264_PROFILE_MAIN,
            width,
            height,
            bit_rate=STREAM_BITRATE,
            dst_frame_rate=STREAM_FPS,
            src_frame_rate=STREAM_FPS,
        )
        self.encoder.Create(self.venc_chn, chn_attr)
        self.encoder.Start(self.venc_chn)
        print("[RTSP] encoder started")

        self.sensor.run()
        print("[RTSP] sensor running")

        self.rtspserver.rtspserver_init(RTSP_PORT)
        self.rtspserver.rtspserver_createsession(
            SESSION_NAME,
            mm.multi_media_type.media_h264,
            False
        )
        self.rtspserver.rtspserver_start()
        print("[RTSP] server started")

        self.running = True
        print("[RTSP] URL:", self.rtspserver.rtspserver_getrtspurl(SESSION_NAME))
        self.init_status_sender()

        try:
            self.init_pest_detector()
        except Exception as e:
            self.det_app = None
            self.labels = []
            print("[AI] Pest detector init failed:", e)
            try:
                sys.print_exception(e)
            except Exception:
                pass

        self.loop()

    def init_status_sender(self):
        try:
            self.status_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.status_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            print("[LAN] UDP broadcast ready:", STATUS_PORT)
        except Exception as e:
            self.status_socket = None
            print("[LAN] UDP init failed:", e)

    def load_json(self, path):
        with open(path, "r") as f:
            return ujson.load(f)

    def init_pest_detector(self):
        deploy_conf = self.load_json(PEST_ROOT_PATH + "/deploy_config.json")
        kmodel_path = PEST_ROOT_PATH + "/" + deploy_conf["kmodel_path"]
        self.labels = deploy_conf["categories"]
        model_conf = deploy_conf["confidence_threshold"]
        nms_threshold = deploy_conf["nms_threshold"]
        model_input_size = deploy_conf["img_size"]
        model_type = deploy_conf["model_type"]

        anchors = []
        if model_type == "AnchorBaseDet":
            anchors = deploy_conf["anchors"][0] + deploy_conf["anchors"][1] + deploy_conf["anchors"][2]

        self.det_app = DetectionApp(
            "video",
            kmodel_path,
            self.labels,
            model_input_size,
            anchors,
            model_type,
            model_conf,
            nms_threshold,
            [AI_WIDTH, AI_HEIGHT],
            [STREAM_WIDTH, STREAM_HEIGHT],
            debug_mode=0
        )
        self.det_app.config_preprocess()
        print("[AI] Pest detector ready:", kmodel_path)
        print("[AI] Labels:", self.labels)

    def loop(self):
        stream_data = StreamData()
        frame_info = k_video_frame_info()

        try:
            while self.running:
                self.frame_count += 1
                img = self.sensor.snapshot(chn=CAM_CHN_ID_0)
                if img == -1:
                    time.sleep_ms(5)
                    continue

                pest_name = "NONE_DETECTED"
                if self.det_app is not None:
                    try:
                        ai_img = self.sensor.snapshot(chn=CAM_CHN_ID_1)
                        if ai_img != -1:
                            ai_np = ai_img.to_numpy_ref()
                            pest_res, pest_name, best_score, best_box = self.run_pest_detection(ai_img, ai_np)
                            if self.frame_count % WITHER_CHECK_INTERVAL == 0:
                                wither_name, y_area, g_area, ratio, plant_box = self.run_wither_detection(ai_np)
                                self.last_plant_box = plant_box
                                if self.frame_count % DEBUG_PRINT_INTERVAL == 0:
                                    print("[WITHER] status:", wither_name, "yellow:", y_area, "green:", g_area, "ratio:", ratio)
                            if best_box is not None:
                                self.draw_detection_box(img, best_box)
                            if self.last_plant_box is not None:
                                self.draw_plant_box(img, self.last_plant_box)
                            if self.frame_count % DEBUG_PRINT_INTERVAL == 0:
                                print("[AI] top1:", pest_name, "score:", best_score)
                    except Exception as e:
                        print("[AI] inference error:", e)

                if pest_name != self.last_pest_name:
                    self.last_pest_name = pest_name
                    print("[AI] Pest:", pest_name)

                if self.wither_confirmed_status != self.last_wither_name:
                    self.last_wither_name = self.wither_confirmed_status
                    print("[WITHER] Plant:", self.wither_confirmed_status)

                if self.frame_count % STATUS_SEND_INTERVAL == 0 or pest_name != self.last_sent_pest or self.wither_confirmed_status != self.last_sent_wither:
                    self.send_status(pest_name, self.wither_confirmed_status)

                frame_info.v_frame.width = img.width()
                frame_info.v_frame.height = img.height()
                frame_info.v_frame.pixel_format = Sensor.YUV420SP
                frame_info.pool_id = img.poolid()
                frame_info.v_frame.phys_addr[0] = img.phyaddr()
                frame_info.v_frame.phys_addr[1] = self.calc_uv_addr(img)

                self.encoder.SendFrame(self.venc_chn, frame_info)
                self.encoder.GetStream(self.venc_chn, stream_data)
                for pack_idx in range(stream_data.pack_cnt):
                    data = bytes(
                        uctypes.bytearray_at(
                            stream_data.data[pack_idx],
                            stream_data.data_size[pack_idx]
                        )
                    )
                    self.rtspserver.rtspserver_sendvideodata(
                        SESSION_NAME,
                        data,
                        stream_data.data_size[pack_idx],
                        1000
                    )
                self.encoder.ReleaseStream(self.venc_chn, stream_data)

                gc.collect()
                time.sleep_ms(10)
                os.exitpoint()

        except BaseException as e:
            print("[RTSP] stream exception:", e)
            try:
                sys.print_exception(e)
            except Exception:
                pass
        finally:
            self.stop()

    def run_pest_detection(self, ai_img, ai_np=None):
        pest_res = None
        pest_name = "NONE_DETECTED"
        best_score = 0.0
        best_box = None

        try:
            if ai_np is None:
                ai_np = ai_img.to_numpy_ref()
            pest_res = self.det_app.run(ai_np)
        except Exception:
            pest_res = self.det_app.run(ai_img)

        if pest_res and isinstance(pest_res, dict) and len(pest_res.get("scores", [])) > 0:
            for i in range(len(pest_res["scores"])):
                score = pest_res["scores"][i]
                if score > best_score:
                    best_score = score
                    label_index = int(pest_res["idx"][i])
                    if label_index >= 0 and label_index < len(self.labels):
                        pest_name = self.labels[label_index]
                    else:
                        pest_name = "UNKNOWN"

                    boxes = pest_res.get("boxes", [])
                    if i < len(boxes):
                        best_box = boxes[i]

            if best_score < PEST_CONFIDENCE_THRESHOLD:
                pest_name = "NONE_DETECTED"
                best_box = None

        return pest_res, pest_name, best_score, best_box

    def run_wither_detection(self, ai_np):
        try:
            if len(ai_np.shape) == 3 and ai_np.shape[0] == 3:
                r = ai_np[0]
                g = ai_np[1]
                b = ai_np[2]
            else:
                r = ai_np[:, :, 0]
                g = ai_np[:, :, 1]
                b = ai_np[:, :, 2]

            # Tighten the color ranges so soil/highlight/background are less likely
            # to be misclassified as "yellow withered leaf".
            green_mask = (g > 72) & (r < 145) & (b < 145) & (g > (r + 16)) & (g > (b + 16))
            yellow_mask = (r > 110) & (g > 95) & (b < 95) & (r >= g) & ((r - g) < 22)

            g_area = int(np.sum(green_mask))
            y_area = int(np.sum(yellow_mask))
            plant_area = int(np.sum(green_mask | yellow_mask))
            plant_box = self.find_plant_box(r, g, b)
        except Exception as e:
            if self.frame_count % DEBUG_PRINT_INTERVAL == 0:
                print("[WITHER] detect error:", e)
            return self.wither_confirmed_status, 0, 0, 0.0, self.last_plant_box

        current_raw_status = "NONE"
        ratio = 0.0
        if plant_area >= WITHER_MIN_PLANT_PIXELS and g_area >= WITHER_MIN_GREEN_PIXELS:
            ratio = y_area / plant_area
            if y_area >= WITHER_MIN_YELLOW_PIXELS and ratio >= WITHER_RATIO_THRESHOLD and y_area > (g_area * 0.55):
                current_raw_status = "WITHERED"
            else:
                current_raw_status = "HEALTHY"

        if current_raw_status == self.wither_temp_status:
            self.wither_temp_count += 1
        else:
            self.wither_temp_status = current_raw_status
            self.wither_temp_count = 1

        if self.wither_temp_count >= WITHER_STABLE_FRAMES:
            self.wither_confirmed_status = self.wither_temp_status

        if self.wither_confirmed_status == "NONE":
            plant_box = None

        return self.wither_confirmed_status, y_area, g_area, ratio, plant_box

    def send_status(self, pest_name, wither_name):
        if self.status_socket is None:
            return

        payload = {
            "pest": pest_name,
            "wither": wither_name
        }
        try:
            self.status_socket.sendto(ujson.dumps(payload).encode("utf-8"), ("255.255.255.255", STATUS_PORT))
            self.last_sent_pest = pest_name
            self.last_sent_wither = wither_name
        except Exception as e:
            if self.frame_count % DEBUG_PRINT_INTERVAL == 0:
                print("[LAN] UDP send error:", e)

    def find_plant_box(self, r, g, b):
        min_x = AI_WIDTH
        min_y = AI_HEIGHT
        max_x = -1
        max_y = -1

        for y in range(0, AI_HEIGHT, PLANT_BOX_SAMPLE_STEP):
            for x in range(0, AI_WIDTH, PLANT_BOX_SAMPLE_STEP):
                rv = int(r[y][x])
                gv = int(g[y][x])
                bv = int(b[y][x])

                is_green = (gv > 48) and (rv < 140) and (bv < 140) and (gv > rv + 10)
                is_yellow = (rv > 56) and (gv > 56) and (bv < 120) and (gv >= rv - 20)
                if is_green or is_yellow:
                    if x < min_x:
                        min_x = x
                    if y < min_y:
                        min_y = y
                    if x > max_x:
                        max_x = x
                    if y > max_y:
                        max_y = y

        if max_x < 0 or max_y < 0:
            return None

        width = max_x - min_x + PLANT_BOX_SAMPLE_STEP
        height = max_y - min_y + PLANT_BOX_SAMPLE_STEP
        if width < 32 or height < 32:
            return None

        return (min_x, min_y, width, height)

    def draw_detection_box(self, img, box):
        try:
            x, y, w, h = self.normalize_box(box)
            if w <= 0 or h <= 0:
                return

            x = x * STREAM_WIDTH // AI_WIDTH
            y = y * STREAM_HEIGHT // AI_HEIGHT
            w = w * STREAM_WIDTH // AI_WIDTH
            h = h * STREAM_HEIGHT // AI_HEIGHT

            if w < 4:
                w = 4
            if h < 4:
                h = 4

            img.draw_rectangle(int(x), int(y), int(w), int(h))
        except Exception as e:
            if self.frame_count % DEBUG_PRINT_INTERVAL == 0:
                print("[AI] draw box error:", e)

    def draw_plant_box(self, img, box):
        try:
            x, y, w, h = box
            x = x * STREAM_WIDTH // AI_WIDTH
            y = y * STREAM_HEIGHT // AI_HEIGHT
            w = w * STREAM_WIDTH // AI_WIDTH
            h = h * STREAM_HEIGHT // AI_HEIGHT

            if w < 4:
                w = 4
            if h < 4:
                h = 4

            img.draw_rectangle(int(x), int(y), int(w), int(h))
        except Exception as e:
            if self.frame_count % DEBUG_PRINT_INTERVAL == 0:
                print("[WITHER] draw plant box error:", e)

    def normalize_box(self, box):
        if len(box) >= 4:
            x1 = int(box[0])
            y1 = int(box[1])
            x2 = int(box[2])
            y2 = int(box[3])
            if x2 > x1 and y2 > y1:
                return x1, y1, x2 - x1, y2 - y1
            return x1, y1, int(box[2]), int(box[3])
        return 0, 0, 0, 0


    def calc_uv_addr(self, img):
        frame_pixels = img.width() * img.height()
        if img.width() == 800 and img.height() == 480:
            return img.phyaddr() + frame_pixels + 1024
        if img.width() == 1920 and img.height() == 1080:
            return img.phyaddr() + frame_pixels + 3072
        if img.width() == 640 and img.height() == 360:
            return img.phyaddr() + frame_pixels + 3072
        return img.phyaddr() + frame_pixels

    def stop(self):
        self.running = False

        try:
            self.sensor.stop()
        except:
            pass

        try:
            self.encoder.Stop(self.venc_chn)
        except:
            pass

        try:
            self.encoder.Destroy(self.venc_chn)
        except:
            pass

        try:
            self.rtspserver.rtspserver_stop()
        except:
            pass

        try:
            self.rtspserver.rtspserver_deinit()
        except:
            pass

        try:
            Display.deinit()
        except:
            pass

        try:
            MediaManager.deinit()
        except:
            pass


if __name__ == "__main__":
    print("[WIFI] Connecting ...")
    sta = connect_wifi(WIFI_SSID, WIFI_PASSWORD)
    print("[WIFI] Connected IP:", sta.ifconfig()[0])

    print("[INIT] Starting simple RTSP server ...")
    server = SimpleRtspServer()
    server.start()
