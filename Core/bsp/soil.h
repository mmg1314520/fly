#ifndef __SOIL_H
#define __SOIL_H

#include "main.h"

// 土壤湿度传感器：PA7 -> ADC2_CH7
void Soil_Init(void);
uint16_t Soil_GetRaw(void);
uint8_t Soil_GetPercent(void);
const char* Soil_GetLevel(void);

#endif
