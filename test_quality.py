from i2sDevice import i2sDevice
import noisereduce as nr
import soundfile as sf
from pedalboard.io import AudioFile
from pedalboard import *


class TestQuality:

    sampleRate:int
    is2Dev:i2sDevice
    originalRec=None

    processedAudio={}

    amplifyDB=40

    def __init__(self, devicename:str, samplerate:int, duration:int):
        self.sampleRate=samplerate
        self.i2sDev = i2sDevice(device=devicename, sample_rate=samplerate, channels=1)
        
        input("Starting Recording, press any key to continue...")
        self.processedAudio["original"] = self.i2sDev.captureStream(duration=duration)

        self.processedAudio["preAmplified"] = self.Amplify(self.processedAudio["original"], self.amplifyDB)

        self.processedAudio["denoised"] = self.ReduceNoise(self.processedAudio["preAmplified"])

        self.processedAudio["enhancedGemini"] = self.enhancedGeminiVoice(self.processedAudio["denoised"])
        
        # self.processedAudio["enhanced"] = self.Enhanced(self.processedAudio["denoised"])

        self.SaveProcessing()





    def Amplify(self, audio, db):
        amplifiedBoard = Pedalboard([
            Gain(gain_db=db)
        ])
        print("Amplifying...")
        amplified = amplifiedBoard(audio, self.sampleRate)
        return amplified
    



    def ReduceNoise(self, audio):
        print("Reduce Noise...")
        reduced_noise = nr.reduce_noise(y=audio, sr=self.sampleRate, stationary=False, prop_decrease=0.60)
        return reduced_noise


    def Enhanced(self, audio):
        enhancedBoard = Pedalboard([
            NoiseGate(threshold_db=-25, ratio=1.5, release_ms=250),
            Compressor(threshold_db=-16, ratio=4),
            LowShelfFilter(cutoff_frequency_hz=400, gain_db=10, q=1),
            Gain(gain_db=2)
        ])

        print("Enhancing...")
        enhanced = enhancedBoard(audio, self.sampleRate)

        return enhanced
    


    def EnhancedGemini(self, audio):
        enhancedBoard = Pedalboard([
            NoiseGate(threshold_db=-35, ratio=2.0, release_ms=200),
            Compressor(threshold_db=-20, ratio=3.0, attack_ms=5, release_ms=100),

            # Equalizzazione con LowShelfFilter e HighShelfFilter (i migliori disponibili per l'EQ in 0.9.17)
            LowShelfFilter(cutoff_frequency_hz=350, gain_db=-5, q=0.707), # Taglio sulle medie basse per chiarezza
            HighShelfFilter(cutoff_frequency_hz=4000, gain_db=3, q=0.707), # Boost dalle 4kHz in su per presenza/brillantezza

            Gain(gain_db=5) # Gain finale
        ])
        enhanced = enhancedBoard(audio, self.sampleRate)
        return enhanced



    def enhancedGeminiVoice(self, audio):

        # 1. Gain iniziale moderato (come precedentemente discusso)
        enhancedBoard = Pedalboard([
            # Noise Gate: Parametri più efficaci per tagliare il rumore tra le parole
            NoiseGate(threshold_db=-35, ratio=2.0, release_ms=200), # Soglia più bassa, rapporto più deciso, rilascio più rapido

            # Compressore: Per uniformare il volume della voce e farla emergere
            Compressor(threshold_db=-20, ratio=3.0, attack_ms=5, release_ms=100), # Parametri più reattivi per la voce

            # --- EQUALIZZAZIONE PER VOCE SQUILLANTE ---

            # 1. Ridurre le frequenze "muddy" (basse-medie)
            # Invece di boostare, tagliamo! Questo è FONDAMENTALE per la brillantezza.
            # Frequenze tra 200 Hz e 500 Hz sono spesso responsabili del suono "ovattato".
            # Qui tagliamo le frequenze SOTTO i 350 Hz.
            LowShelfFilter(cutoff_frequency_hz=350, gain_db=-6, q=0.707), # Taglia le basse-medie problematiche (-6dB è un taglio significativo)

            # 2. Aumentare le frequenze di presenza e brillantezza (alte-medie e alte)
            # Questo è dove si aggiunge lo "squillante".
            # Frequenze tra 2 kHz e 8 kHz sono cruciali per la chiarezza e la brillantezza della voce.
            # Useremo un HighShelfFilter per aumentare le frequenze SOPRA una certa soglia.
            HighShelfFilter(cutoff_frequency_hz=3000, gain_db=5, q=0.707), # Boost significativo sopra i 3kHz per chiarezza e "aria"
            # Potresti anche provare:
            # HighShelfFilter(cutoff_frequency_hz=5000, gain_db=4, q=0.707), # Un boost più in alto per un'aria più marcata

            # Gain finale: Regola il volume complessivo dell'output
            Gain(gain_db=5) # Aggiusta questo per il volume desiderato
        ])
        enhanced = enhancedBoard(audio, self.sampleRate)
        return enhanced





    def SaveProcessing(self):
        i:int = 1
        for k in self.processedAudio.keys():
            aud = self.processedAudio[k]
            filename = f"{str(i)}_{k}.wav"
            print(f"Writing file {filename}...")
            sf.write(filename, data=aud, samplerate=self.sampleRate)
            i = i+1




tq = TestQuality(devicename="googlevoicehat", samplerate=48000, duration=15)
