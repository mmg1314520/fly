#include "sg90.h"
#include "tim.h"

extern TIM_HandleTypeDef htim2;

#define SG90_PERIOD_US         20000U
#define SG90_MIN_PULSE_US        500U
#define SG90_MAX_PULSE_US       2500U
#define SG90_CENTER_PULSE_US    1500U

static uint8_t sg90_ready = 0;

static void SG90_StartIfNeeded(void)
{
    if(sg90_ready)
    {
        return;
    }

    __HAL_TIM_SET_PRESCALER(&htim2, 71U);
    __HAL_TIM_SET_AUTORELOAD(&htim2, SG90_PERIOD_US - 1U);
    __HAL_TIM_SET_COUNTER(&htim2, 0U);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, SG90_CENTER_PULSE_US);
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);
    sg90_ready = 1;
}

static void SG90_WritePulseUs(uint16_t pulse_us)
{
    if(pulse_us < SG90_MIN_PULSE_US)
    {
        pulse_us = SG90_MIN_PULSE_US;
    }
    if(pulse_us > SG90_MAX_PULSE_US)
    {
        pulse_us = SG90_MAX_PULSE_US;
    }

    SG90_StartIfNeeded();
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, pulse_us);
}

void SG90_Init(void)
{
    SG90_StartIfNeeded();
    HAL_Delay(100);
    SG90_WritePulseUs(SG90_CENTER_PULSE_US);
    HAL_Delay(300);
}

void SG90_SetAngle(uint8_t angle)
{
    uint32_t pulse_us;

    if(angle > 180U)
    {
        angle = 180U;
    }

    pulse_us = SG90_MIN_PULSE_US +
               ((uint32_t)angle * (SG90_MAX_PULSE_US - SG90_MIN_PULSE_US) / 180U);
    SG90_WritePulseUs((uint16_t)pulse_us);
}

void SkyWindow_Close(void)
{
    SG90_SetAngle(0U);
}

void SkyWindow_Open(void)
{
    SG90_SetAngle(90U);
}

void SkyWindow_FullOpen(void)
{
    SG90_SetAngle(180U);
}
