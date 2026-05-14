#ifndef __jw01_co2_H
#define __jw01_co2_H

#include "main.h"

extern uint8_t Usart2_RxPacket[6];
extern uint8_t Usart2_RxFlag;
extern uint16_t CO2_Value;

void USART2_Init(void);
void CO2_GetData(uint16_t *data);

#endif
