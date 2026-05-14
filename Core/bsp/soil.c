#include "soil.h"
#include "adc.h"
#include "stdio.h"

// 土壤湿度校准参数
#define SOIL_DRY    2800   // 干燥
#define SOIL_WET    1000   // 湿润

void Soil_Init(void)
{
    printf("[Soil] PA7 ADC2 CH7 Init OK\r\n");
}

// 稳定读取土壤ADC值
uint16_t Soil_GetRaw(void)
{
    uint32_t sum = 0;
    int i;

    for(i=0; i<10; i++)
    {
        HAL_ADC_Start(&hadc2);
        if(HAL_ADC_PollForConversion(&hadc2, 10) == HAL_OK)
        {
            sum += HAL_ADC_GetValue(&hadc2);
        }
        HAL_ADC_Stop(&hadc2);
        HAL_Delay(1);
    }

    return sum / 10;
}

// 获取湿度百分比 0~100%
uint8_t Soil_GetPercent(void)
{
    uint16_t raw = Soil_GetRaw();
    uint8_t per;

    if(raw >= SOIL_DRY) return 0;
    if(raw <= SOIL_WET) return 100;

    per = (SOIL_DRY - raw) * 100 / (SOIL_DRY - SOIL_WET);
    return per;
}

