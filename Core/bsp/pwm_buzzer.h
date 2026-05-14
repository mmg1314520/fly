#ifndef __PWM_BUZZER_H
#define __PWM_BUZZER_H

#include "main.h"

// 驱虫专用频率定义
#define FREQ_500HZ     500
#define FREQ_800HZ     800
#define FREQ_1200HZ    1200
#define FREQ_1500HZ    1500
#define FREQ_2000HZ    2000

// 初始化
void Buzzer_PWM_Init(void);

// 设置频率 + 占空比(0~100)
void Buzzer_SetFreq(uint16_t freq, uint8_t duty);

// 开关
void Buzzer_Start(void);
void Buzzer_Stop(void);

// 驱虫模式
void Buzzer_Mosquito_Mode(void);   // 驱蚊子
void Buzzer_Fly_Mode(void);        // 驱苍蝇
void Buzzer_StopAll(void);
void youchong_deng_off(void );
void youchong_deng_on(void );
void shuibeng_off(void );
void shuibeng_on(void );
void fan_off(void );
	void fan_on(void );
#endif

