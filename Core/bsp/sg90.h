#ifndef __SG90_H
#define __SG90_H

#include "main.h"

// 天窗角度定义
#define SKY_WINDOW_CLOSE    0    // 关闭 0°
#define SKY_WINDOW_OPEN     90   // 半开 90°
#define SKY_WINDOW_FULL     180  // 全开 180°

void SG90_Init(void);                // 初始化
void SG90_SetAngle(uint8_t angle);   // 设置角度 0~180

// 天窗专用函数
void SkyWindow_Close(void);
void SkyWindow_Open(void);
void SkyWindow_FullOpen(void);

#endif
