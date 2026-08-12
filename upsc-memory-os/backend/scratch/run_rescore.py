import asyncio
from services.prediction.jobs import daily_urgency_rescore

async def run():
    print("Forcing the urgency rescore to run manually...")
    try:
        await daily_urgency_rescore()
        print("Manual run complete!")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(run())
