import sounddevice as sd
from scipy.io.wavfile import write
import wavio as wv
from datetime import datetime
import time
from loguru import logger
import soundfile as sf
import os
import re

chunks = []
interrupt = False
regExDT = "^([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})([0-9]{2})$"



def testChunk():
    now = datetime.now()
    init = now.strftime("%Y%m%d%H%M%S")
    recording = sd.rec(int(10 * 48000), 
                samplerate=48000, channels=1)
    sd.wait()
    sf.write("test.wav", recording, 48000)


if __name__ == "__main__":
    testChunk()