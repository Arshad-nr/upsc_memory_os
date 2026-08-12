import asyncio
from services.llm import call_gemini
async def main():
    for model in ['gemini-1.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-flash']:
        print(f'\nTesting {model}...')
        for i in range(3):
            try:
                res = await call_gemini('Hi', model=model)
                if res == '{}':
                    print(f'  Call {i+1}: FAILED (caught by llm.py error handler)')
                else:
                    print(f'  Call {i+1}: SUCCESS')
            except Exception as e:
                print(f'  Call {i+1}: EXCEPTION {e}')
if __name__ == '__main__':
    asyncio.run(main())
