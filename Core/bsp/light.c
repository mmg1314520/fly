#include "light.h"
#include "adc.h"
#include "stdio.h"

#define LIGHT_MIN    500
#define LIGHT_MAX    3500

void LightSensor_Init(void)
{
    // CubeMX 已经初始化好了
    printf("[Light] PB1 ADC1 CH9 Init OK\r\n");
}

// 稳定读取ADC（多次采样取平均）
uint16_t LightSensor_GetRawValue(void)
{
    uint32_t adc_sum = 0;
    uint8_t i;

    // 采样 10 次取平均 → 超级稳定
    for(i=0; i<10; i++)
    {
        HAL_ADC_Start(&hadc1);
        if(HAL_ADC_PollForConversion(&hadc1, 10) == HAL_OK)
        {
            adc_sum += HAL_ADC_GetValue(&hadc1);
        }
        HAL_ADC_Stop(&hadc1);
        HAL_Delay(1);
    }

    return adc_sum / 10;
}

uint8_t LightSensor_GetPercentage(void)
{
    uint16_t raw = LightSensor_GetRawValue();
    if(raw <= LIGHT_MIN) return 0;
    if(raw >= LIGHT_MAX) return 100;
    return 100-((raw - LIGHT_MIN) * 100 / (LIGHT_MAX - LIGHT_MIN));
}

