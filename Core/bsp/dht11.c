#include "dht11.h"

#define DHT11_GPIO_Port GPIOB
#define DHT11_Pin GPIO_PIN_12
#define DHT11_TIMEOUT_US 120U

static void DHT11_DelayUs(uint32_t us)
{
    uint32_t start = SysTick->VAL;
    uint32_t ticks = us * (SystemCoreClock / 1000000U);
    uint32_t reload = SysTick->LOAD + 1U;
    uint32_t elapsed = 0;
    uint32_t now;

    while(elapsed < ticks)
    {
        now = SysTick->VAL;
        if(start >= now)
        {
            elapsed += start - now;
        }
        else
        {
            elapsed += start + (reload - now);
        }
        start = now;
    }
}

static void DHT11_SetPinOutput(void)
{
    GPIO_InitTypeDef gpio = {0};

    gpio.Pin = DHT11_Pin;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_PULLUP;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(DHT11_GPIO_Port, &gpio);
}

static void DHT11_SetPinInput(void)
{
    GPIO_InitTypeDef gpio = {0};

    gpio.Pin = DHT11_Pin;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(DHT11_GPIO_Port, &gpio);
}

static GPIO_PinState DHT11_ReadPin(void)
{
    return HAL_GPIO_ReadPin(DHT11_GPIO_Port, DHT11_Pin);
}

static uint8_t DHT11_WaitForLevel(GPIO_PinState level, uint32_t timeout_us)
{
    while(timeout_us--)
    {
        if(DHT11_ReadPin() == level)
        {
            return 1;
        }
        DHT11_DelayUs(1);
    }

    return 0;
}

static void DHT11_StartSignal(void)
{
    DHT11_SetPinOutput();
    HAL_GPIO_WritePin(DHT11_GPIO_Port, DHT11_Pin, GPIO_PIN_RESET);
    HAL_Delay(20);
    HAL_GPIO_WritePin(DHT11_GPIO_Port, DHT11_Pin, GPIO_PIN_SET);
    DHT11_DelayUs(30);
    DHT11_SetPinInput();
}

static uint8_t DHT11_CheckResponse(void)
{
    if(!DHT11_WaitForLevel(GPIO_PIN_RESET, DHT11_TIMEOUT_US))
    {
        return 0;
    }

    if(!DHT11_WaitForLevel(GPIO_PIN_SET, DHT11_TIMEOUT_US))
    {
        return 0;
    }

    if(!DHT11_WaitForLevel(GPIO_PIN_RESET, DHT11_TIMEOUT_US))
    {
        return 0;
    }

    return 1;
}

static uint8_t DHT11_ReadBit(uint8_t *bit)
{
    if(!DHT11_WaitForLevel(GPIO_PIN_SET, DHT11_TIMEOUT_US))
    {
        return 0;
    }

    DHT11_DelayUs(40);
    *bit = (DHT11_ReadPin() == GPIO_PIN_SET) ? 1U : 0U;

    if(!DHT11_WaitForLevel(GPIO_PIN_RESET, DHT11_TIMEOUT_US))
    {
        return 0;
    }

    return 1;
}

static uint8_t DHT11_ReadByte(uint8_t *data)
{
    uint8_t i;
    uint8_t bit;
    uint8_t value = 0;

    for(i = 0; i < 8; i++)
    {
        value <<= 1;
        if(!DHT11_ReadBit(&bit))
        {
            return 0;
        }
        value |= bit;
    }

    *data = value;
    return 1;
}

uint8_t DHT11_Init(void)
{
    __HAL_RCC_GPIOB_CLK_ENABLE();
    DHT11_SetPinInput();
    HAL_Delay(100);

    DHT11_StartSignal();
    return DHT11_CheckResponse();
}

uint8_t DHT11_ReadData(uint8_t *humi, uint8_t *temp)
{
    uint8_t i;
    uint8_t data[5] = {0};
    uint32_t primask;

    if(humi == NULL || temp == NULL)
    {
        return 0;
    }

    DHT11_StartSignal();

    primask = __get_PRIMASK();
    __disable_irq();

    if(!DHT11_CheckResponse())
    {
        if(!primask)
        {
            __enable_irq();
        }
        return 0;
    }

    for(i = 0; i < 5; i++)
    {
        if(!DHT11_ReadByte(&data[i]))
        {
            if(!primask)
            {
                __enable_irq();
            }
            return 0;
        }
    }

    if(!primask)
    {
        __enable_irq();
    }

    if((uint8_t)(data[0] + data[1] + data[2] + data[3]) != data[4])
    {
        return 0;
    }

    *humi = data[0];
    *temp = data[2];
    return 1;
}
