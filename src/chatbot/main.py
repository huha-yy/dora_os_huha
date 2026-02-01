import atexit
import asyncio
import json
from pathlib import Path
import sys
from server import WebSocketServer
from loguru import logger
import uvicorn
import click

def init_logger(log_level: str="INFO")->None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | {message}",
        colorize=True,
    )

    logger.add(
        "logs/debug_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message} | {extra}",
        backtrace=True,
        diagnose=True,
    )


@logger.catch
def run_chatbot(log_level: str="INFO")->None:
    init_logger(log_level)
    print("Running chatbot...")
    config_path = Path(__file__).parent / "config.json"
    config = json.load(open(config_path))
    server = WebSocketServer(config)
    
    # Register cleanup with the instance method
    atexit.register(server.clean_cache)

    host = config.get("host", "0.0.0.0")
    port = config.get("port", 8000)
    
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        app=server.app,
        host=host,
        port=port,
        log_level=log_level.lower(),
    )

@click.command()
@click.option("--log-level", type=str, default="INFO", help="Log level")
def main(log_level):
    run_chatbot(log_level)

if __name__ == "__main__":
    main()