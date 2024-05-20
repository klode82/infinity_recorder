import sounddevice as sd
from scipy.io.wavfile import write
import wavio as wv
import uuid
import tracemalloc
from datetime import datetime
import time
from threading import Thread
from loguru import logger
import soundfile as sf
import os
import pyaudio
  
config = {
    "freq": 48000,
    "chunk_duration": 30,
    "dest_folder":"./audio/",
    "prefix_name":"record_",
    "extension":"ogg",
    "counter":0
}

chunks = []
interrupt = False



def GetHumanReadable(size,precision=2):
    suffixes=['B','KB','MB','GB','TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1 #increment the index of the suffix
        size = size/1024.0 #apply the division
    return "%.*f%s"%(precision,size,suffixes[suffixIndex])

def recordChunk():
    now = datetime.now()
    init = now.strftime("%Y%m%d%H%M%S")
    recording = sd.rec(int(config["chunk_duration"] * config["freq"]), 
                samplerate=config["freq"], channels=1)
    sd.wait()
    chunks.append({"init":init, "data":recording})
    config["counter"] += 1
    logger.info(f'Acquired {config["counter"]} chunks...')
    del recording
        

def saveChunk():
    saving_thread = Thread(
        target=_save,
        daemon=True,
    )
    saving_thread.start()


def _save():
    while True:
        if len(chunks) > 0:
            saved = False
            while saved is False:
                chunk = chunks[len(chunks)-1]
                filename = config["prefix_name"] + chunk["init"] + "." + config["extension"]
                subfolder = chunk["init"][0:8]
                if not os.path.isdir(config["dest_folder"] + subfolder):
                    os.mkdir(config["dest_folder"] + subfolder)

                logger.info(f'Saving {filename}...')
                
                try:
                    sf.write(config["dest_folder"] + subfolder + "/" + filename, chunk["data"], config["freq"])
                    saved = True
                    chunks.pop()
                except Exception as e:
                    logger.error('Saving error - retrying... ' + str(e))
                    time.sleep(2)
        time.sleep(30)
        memUsed = tracemalloc.get_traced_memory()
        logger.info("Memory: " + GetHumanReadable(memUsed[1]))


def main():
    tracemalloc.start()
    try:
        logger.info("Starting recording...")
        saveChunk()
        while True:
            recordChunk()
    except KeyboardInterrupt:
        while len(chunks) > 0:
            time.sleep(3)
    finally:
        while len(chunks) > 0:
            time.sleep(3)
    tracemalloc.stop()

if __name__ == "__main__":
    main()
