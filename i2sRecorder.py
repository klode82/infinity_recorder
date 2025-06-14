import numpy as np
import soundfile as sf
from pydub import AudioSegment
import threading
import queue
import time
import os
import traceback
from pathlib import Path

from i2sDevice import i2sDevice

from datetime import datetime

import noisereduce as nr
from pedalboard import *



class i2sRecorder:

    FrameRate:int = 48000
    SingleTrackDuration:int = 30
    ProcessingTrackDuration:int = 600
    ChannelToKeep:int = 0
    Amplify_dB:int = 40

    AudioTracksDir:str = "audio_logs"
    ProcessedDir:str = "processed_audio"
    TrackFileQueue:queue.Queue
    BufferBlocks = []
    FileBlocks = []

    i2sAudioDevice:str = "googlevoicehat"

    AmplifyFactor:int

    i2sDev:i2sDevice

    def __init__(self):

        print("Preparing Folder...")
        os.makedirs(self.AudioTracksDir, exist_ok=True)
        os.makedirs(self.ProcessedDir, exist_ok=True)

        print("Preparing Device...")
        self.i2sDev = i2sDevice(
            device=self.i2sAudioDevice,
            sample_rate=self.FrameRate,
            channels=1)
        
        if not self.i2sDev.deviceReady:
            raise Exception(f"Unable to find Device {self.i2sAudioDevice}.")
        
        print("Preparing configuration...")
        self.AmplifyFactor = 10 ** (self.Amplify_dB / 20)
        self.TrackFileQueue = queue.Queue()

        

    def startRecording(self):
        self.RecordingThread = threading.Thread(target=self.recordWorker, daemon=True)

        self.ProcessingThread = threading.Thread(target=self.processAudioWorker, daemon=True)

        self.RecordingThread.start()
        self.ProcessingThread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Terminazione richiesta dall'utente.")
    



    def recordTrack(self, duration:int=30):
        singleTrack = self.i2sDev.captureStream(duration=duration)
        return singleTrack




    def recordWorker(self):
        """Registra WAV stereo da device, salva file da 5s e mette in coda il path"""
        while True:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.AudioTracksDir, f"rec_{timestamp}_stereo.wav")
            
            print(f"[Recorder] Registrazione in corso: {filename}")
            
            singleTrack = self.i2sDev.captureStream(duration=self.SingleTrackDuration)

            saveThread = threading.Thread(target=self.saveTrack, args=(filename, singleTrack), daemon=True)
            saveThread.start()

            
    
    def saveTrack(self, filename, track):
        sf.write(filename, track, self.FrameRate, subtype='FLOAT')
        self.TrackFileQueue.put(filename)




    def processAudioWorker(self):
        """Consuma file WAV, filtra, amplifica e salva gruppi da 10 minuti in OGG"""
        block_count = 0
        group_start_time = None

        while True:
            filename = self.TrackFileQueue.get()
            try:
                print(f"[Processor] Elaborazione file: {filename}")
                data, fs = sf.read(filename)
                
                enhanced = self.enhancedAudio(data)
                
                
                # Aggiungi blocco al buffer
                self.BufferBlocks.append(enhanced)
                self.FileBlocks.append(filename)
                block_count += 1

                # Imposta il tempo iniziale per il nome file del gruppo
                if group_start_time is None:
                    group_start_time = datetime.now().strftime("%Y%m%d_%H%M%S")

                # Quando il buffer raggiunge 120 blocchi (10 minuti)
                if block_count == (self.ProcessingTrackDuration / self.SingleTrackDuration):
                    print(f"[Processor] Salvando gruppo da {self.ProcessingTrackDuration / 60} minuti: {group_start_time}")
                    combined = np.concatenate(self.BufferBlocks)

                    # Salva WAV mono temporaneo del gruppo
                    wav_group_path = os.path.join(self.ProcessedDir, f"group_{group_start_time}_mono.wav")
                    sf.write(wav_group_path, combined, fs, subtype='FLOAT')

                    # Converti in OGG
                    audio_segment = AudioSegment.from_wav(wav_group_path)

                    # Preparazione cartella di destinazione con la data odierna
                    destFolder = os.path.join(self.ProcessedDir, datetime.now().strftime("%Y%m%d"))
                    Path(destFolder).mkdir(parents=True,exist_ok=True)

                    ogg_path = os.path.join(destFolder, f"group_{group_start_time}.m4a")
                    audio_segment.export(ogg_path, format="ipod", bitrate="128k")
                    
                    print(f"[Processor] Gruppo da 10 minuti salvato: {ogg_path}")

                    # Pulizia temporanei
                    os.remove(wav_group_path)

                    # Pulizia AudioBlocks
                    for f in self.FileBlocks:
                        try:
                            os.remove(f)
                        except:
                            print(f"Impossibile eliminare il file {f}")

                    # Reset buffer
                    self.BufferBlocks = []
                    self.FileBlocks = []
                    block_count = 0
                    group_start_time = None

            except Exception as e:
                print(f"[Processor] Errore durante l'elaborazione: {e}")
                traceback.print_exc()

            finally:
                self.TrackFileQueue.task_done()



    def enhancedAudio(self, data):

        amplifiedBoard = Pedalboard([
            Gain(gain_db=40)
        ])
        amplified = amplifiedBoard(data, self.FrameRate)
    

        reduced_noise = nr.reduce_noise(y=amplified, sr=self.FrameRate, stationary=False, prop_decrease=0.60)


        enhancedBoard = Pedalboard([
            NoiseGate(threshold_db=-35, ratio=2.0, release_ms=200), # Soglia più bassa, rapporto più deciso, rilascio più rapido
            Compressor(threshold_db=-20, ratio=3.0, attack_ms=5, release_ms=100), # Parametri più reattivi per la voce
            LowShelfFilter(cutoff_frequency_hz=350, gain_db=-6, q=0.707), # Taglia le basse-medie problematiche (-6dB è un taglio significativo)
            HighShelfFilter(cutoff_frequency_hz=3000, gain_db=5, q=0.707), # Boost significativo sopra i 3kHz per chiarezza e "aria"
            Gain(gain_db=5) # Aggiusta questo per il volume desiderato
        ])
        enhanced = enhancedBoard(reduced_noise, self.FrameRate)
        return enhanced




