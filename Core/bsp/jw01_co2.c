#include "jw01_co2.h"

uint8_t  Usart2_RxPacket[6] = {0};
uint8_t  Usart2_RxFlag = 0;
uint16_t CO2_Value = 0;
#include  <string.h>
#include <stdio.h>

extern uint8_t u3_rx_buf[128];
extern uint8_t u3_rx_ch;
extern uint8_t u3_rx_flag;
extern uint16_t u3_rx_cnt ;
extern uint8_t u3_rx_buf[128];
extern UART_HandleTypeDef huart2;
extern UART_HandleTypeDef huart3;
void USART2_Init(void)
{
    // CubeMX 已完成 USART2 和引脚初始化，这里只开启中断接收
    HAL_UART_Receive_IT(&huart2, &Usart2_RxPacket[0], 1);
}
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    // -------- USART2：CO2 传感器（你原来的代码，完全不动）--------
    if(huart->Instance == USART2)
    {
        static uint8_t state = 0;
        static uint8_t cnt = 0;
        uint8_t ch = Usart2_RxPacket[cnt];

        if(state == 0)
        {
            if(ch == 0x2C)
            {
                Usart2_RxPacket[0] = ch;
                cnt = 1;
                state = 1;
            }
        }
        else if(state == 1)
        {
            Usart2_RxPacket[cnt++] = ch;
            if(cnt >= 6)
            {
                if(Usart2_RxPacket[3]==0x03 && Usart2_RxPacket[4]==0xFF)
                {
                    uint8_t sum=Usart2_RxPacket[0]+Usart2_RxPacket[1]+Usart2_RxPacket[2]+
                    Usart2_RxPacket[3]+Usart2_RxPacket[4];
                    if(Usart2_RxPacket[5]==sum) Usart2_RxFlag=1;
                }
                state=0; cnt=0;
            }
        }
        HAL_UART_Receive_IT(&huart2, &Usart2_RxPacket[cnt], 1);
    }

    // -------- USART3：Linux 通信（修复版！）--------
    if(huart->Instance == USART3)
    {
        // 外部声明 main.c 的变量（必须写！）
        extern uint8_t  u3_rx_buf[];
        extern uint8_t  u3_rx_ch;
        extern uint16_t u3_rx_cnt;
        extern uint8_t  u3_rx_done;

        // 收到换行，代表一帧结束
        if(u3_rx_ch == '\n' || u3_rx_ch == '\r')
        {
            u3_rx_done = 1;
        }
        else
        {
            if(u3_rx_cnt < 127)
            {
                u3_rx_buf[u3_rx_cnt++] = u3_rx_ch;
            }
            else
            {
                u3_rx_cnt = 0;
                // 删掉报错的 memset，只需要计数清零即可
            }
        }

        // 继续接收
        HAL_UART_Receive_IT(&huart3, &u3_rx_ch, 1);
    }
}
// 获取CO2浓度
void CO2_GetData(uint16_t *data)
{
    if(Usart2_RxFlag == 1)
    {
        *data = (Usart2_RxPacket[1] << 8) | Usart2_RxPacket[2];
        Usart2_RxFlag = 0;
    }
}


