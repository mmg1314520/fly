#include "pwm_buzzer.h"
#include "tim.h"

extern TIM_HandleTypeDef htim1;

// 初始化 PWM
void Buzzer_PWM_Init(void)
{
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_4);
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, 0);
}

// 设置频率和占空比
void Buzzer_SetFreq(uint16_t freq, uint8_t duty)
{
    if(freq == 0)
    {
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, 0);
        return;
    }

    uint32_t timer_clk = 72000000;
    uint32_t psc = 71;
    uint32_t arr = (timer_clk / ((psc + 1) * freq)) - 1;

    if(arr > 65535) arr = 65535;
    if(arr < 1) arr = 1;

    __HAL_TIM_SET_AUTORELOAD(&htim1, arr);
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, arr * duty / 100);
}

// 开启
void Buzzer_Start(void)
{
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_4);
}

// 停止
void Buzzer_Stop(void)
{
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, 0);
}

// ==================== 驱虫专用模式 ====================
// 驱蚊子：500~800Hz 交替
void Buzzer_Mosquito_Mode(void)
{
    Buzzer_SetFreq(650, 50);
    Buzzer_Start();
}

// 驱苍蝇/飞虫：1200~1800Hz
void Buzzer_Fly_Mode(void)
{
    Buzzer_SetFreq(1500, 50);
    Buzzer_Start();
}

// 关闭所有
void Buzzer_StopAll(void)
{
    Buzzer_Stop();
}

void youchong_deng_on(void )
{
	HAL_GPIO_WritePin (GPIOA,GPIO_PIN_8 ,GPIO_PIN_SET);
}

void youchong_deng_off(void )
{
	HAL_GPIO_WritePin (GPIOA,GPIO_PIN_8 ,GPIO_PIN_RESET);
}

void shuibeng_on(void )
{
	HAL_GPIO_WritePin (GPIOA,GPIO_PIN_12 ,GPIO_PIN_SET);
}

void shuibeng_off(void )
{
	HAL_GPIO_WritePin (GPIOA,GPIO_PIN_12 ,GPIO_PIN_RESET);
}

void fan_on(void )
{
	HAL_GPIO_WritePin (GPIOB,GPIO_PIN_0 ,GPIO_PIN_SET);
}

void fan_off(void )
{
	HAL_GPIO_WritePin (GPIOB,GPIO_PIN_0 ,GPIO_PIN_RESET);
}
