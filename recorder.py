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
import re
from pydub import AudioSegment
#import pyaudio
  
config = {
    "freq": 48000,
    "chunk_duration": 30,
    "chunk_folder":"./chunks/",
    "dest_folder":"./audio/",
    "prefix_name":"record_",
    "extension":"ogg",
    "counter":0
}

chunks = []
interrupt = False
regExDT = "^([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})$"



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
        target=_saveChunk,
        daemon=True,
    )
    saving_thread.start()

def saveRecords():
    saving_thread = Thread(
        target=_saveRecords,
        daemon=True,
    )
    saving_thread.start()




def _saveChunk():
    while True:
        if len(chunks) > 0:
            saved = False
            while saved is False:
                chunk = chunks[len(chunks)-1]
                filename = "chunk." + chunk["init"] + ".wav"
                subfolder = chunk["init"][0:8]
                if not os.path.isdir(config["chunk_folder"] + subfolder):
                    os.makeidrs(config["chunk_folder"] + subfolder, exist_ok=True)

                logger.info(f'Chunk Saving {filename}...')
                
                try:
                    sf.write(config["chunk_folder"] + subfolder + "/" + filename, chunk["data"], config["freq"])
                    saved = True
                    chunks.pop()
                except Exception as e:
                    logger.error('Saving error - retrying... ' + str(e))
                    time.sleep(2)
        time.sleep(30)
        memUsed = tracemalloc.get_traced_memory()
        logger.info("Memory: " + GetHumanReadable(memUsed[1]))



def _sortdir(directory):
    items = os.listdir(directory)
    sorted_items = sorted(items)
    return sorted_items



def _saveRecords():
    while True:
        now = datetime.now()
        nowFolder = now.strftime("%Y%m%d")
        chunksDir = _sortdir(config["chunk_folder"])
        chunksDir = sorted(chunksDir)

        for cdir in chunksDir:
            chunkDirPath = config["chunk_folder"] + cdir
            chunkFiles = _sortdir(chunkDirPath)
            if len(chunkFiles) == 0 and cdir != nowFolder:
                os.removedirs(chunkDirPath)
                time.sleep(10)
                break
            
            if len(chunkFiles) > 10:
                blockFiles = chunkFiles[slice(10)]
                _joinChunks(chunkDirPath, blockFiles)
            else:
                if cdir != nowFolder :
                    _joinChunks(chunkDirPath, chunkFiles)

        time.sleep(30)


def _joinChunks(chunkDirPath, files):
    chunkDirPath = chunkDirPath + "/"
    infoFile = files[0].split(".")
    infoData = infoFile[1]
    infoDateTime = re.findall(regExDT, infoData)
    audioFolder = infoData[0:8]


    audioFileName = str(infoDateTime[0]) + "-" + \
            str(infoDateTime[1]) + "-" + \
            str(infoDateTime[2]) + "_" + \
            str(infoDateTime[3]) + "-" + \
            str(infoDateTime[4]) + "-" + \
            str(infoDateTime[5]) + ".ogg"
    audioFile = None
    _aud = None
    for f in files:
        if audioFile is None:
            audioFile = AudioSegment.from_file(chunkDirPath + f, format="wav")
        else:
            _aud = AudioSegment.from_file(chunkDirPath + f, format="wav")
            audioFile = audioFile + _aud

    logger.info("Saving file " + audioFileName + " in " + audioFolder + "...")
    if not os.path.isdir(config["dest_folder"] + audioFolder):
        os.makedirs(config["dest_folder"] + audioFolder, exist_ok=True)
    file_handle = audioFile.export(config["dest_folder"] + audioFolder + "/" + audioFileName, format="ogg")

    for f in files:
        os.remove(chunkDirPath + f)
    del audioFile
    del _aud

    




def main():
    tracemalloc.start()
    try:
        logger.info("Starting recording...")
        saveChunk()
        saveRecords()
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
