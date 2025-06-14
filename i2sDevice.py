import sounddevice as sd
import numpy as np
import soundfile as sf
from pydub import AudioSegment
import threading
import queue
import time
import os
import json
import traceback
import noisereduce as nr
from pathlib import Path

from datetime import datetime




class i2sDevice:

    deviceSearchingTerm:str
    deviceIndex:int
    deviceSampleRate:int
    deviceChannels:int


    outputStream:None


    def __init__(self, device:str, sample_rate:int, channels:int):
        self.deviceSearchingTerm = device
        self.deviceSampleRate = sample_rate
        self.deviceChannels = channels

        self.getDevice()



    def __searchDeviceIndex(self):
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            if self.deviceSearchingTerm.lower() in dev['name'].lower() and dev['max_input_channels'] >= 2:
                return i
        raise RuntimeError(f"Device audio using terms '{self.deviceSearchingTerm}' not Found.")




    def getDevice(self):
        self.deviceIndex = self.__searchDeviceIndex()
        if self.deviceIndex is None:
            print(f"Device {self.deviceSearchingTerm} audio not Found.")
        else:
            print(f"Device {self.deviceSearchingTerm} audio Found on {self.deviceIndex}")



    def deviceReady(self):
        return self.deviceIndex is not None




    def captureStream(self, duration:int):
        if not self.deviceReady:
            print("No stream recorded, device not found.")
            return
        
        stream = sd.rec(
            frames = int(duration * self.deviceSampleRate),
            samplerate = self.deviceSampleRate,
            channels = self.deviceChannels,
            dtype = 'float32',
            device = self.deviceIndex 
        )
        sd.wait()
        outputAudio = stream.flatten()
        self.outputStream = outputAudio
        return outputAudio
    


    def saveAudio(self, fullpath:str, bitrate:int, bitrate_mode:str='CONSTANT'):
        if self.outputStream is not None:
            sf.write(fullpath, self.outputStream, bitrate=bitrate, bitrate_mode=bitrate_mode)


    
