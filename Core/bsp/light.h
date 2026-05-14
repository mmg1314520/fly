#ifndef __LIGHT_H
#define __LIGHT_H

#include "main.h"

void LightSensor_Init(void);
uint16_t LightSensor_GetRawValue(void);
uint8_t LightSensor_GetPercentage(void);

#endif
