import asyncio
from services.llm import call_gemini
async def main():
    print('Testing call_gemini...')
    res = await call_gemini('Hi', model='gemini-2.5-flash-lite')
    print(f'Result: {res[:50]}...')
if __name__ == '__main__':
    asyncio.run(main())
