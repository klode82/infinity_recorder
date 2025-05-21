import sounddevice as sd
import numpy as np
import scipy.signal
import soundfile as sf
from pydub import AudioSegment
import threading
import queue
import time
import os
import json
from datetime import datetime

# Parametri
FS = 48000
DURATION = 5  # secondi
CHANNEL_TO_KEEP = 0  # canale da estrarre (0=sinistro)
AMPLIFY_DB = 60
AUDIO_DIR = "audio_logs"
PROCESSED_DIR = "processed_audio"
FILTER_INFO_FILE = "filter_fft_log.json"
AUDIODEVICE = "googlevoicehat"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Amplificazione lineare
amplify_factor = 10 ** (AMPLIFY_DB / 20)

# Queue per comunicazione tra thread
file_queue = queue.Queue()


def record_noise_profile(device_idx, duration=5):
    print("[Noise] Registrazione rumore ambiente...")
    noise = sd.rec(int(duration * FS), samplerate=FS, channels=1, dtype='float32', device=device_idx)
    sd.wait()
    noise = noise.flatten()
    print("[Noise] Rumore registrato.")
    return noise

def record_worker(device_idx, q):
    """Registra WAV stereo da device, salva file da 5s e mette in coda il path"""
    while True:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(AUDIO_DIR, f"rec_{timestamp}_stereo.wav")
        print(f"[Recorder] Registrazione in corso: {filename}")
        recording = sd.rec(int(DURATION * FS), samplerate=FS, channels=2, dtype='float32', device=device_idx)
        sd.wait()
        sf.write(filename, recording, FS, subtype='FLOAT')
        q.put(filename)
        print(f"[Recorder] Registrazione salvata e messa in coda: {filename}")

def record_worker_stream(device_idx, q):
    """Registra continuamente in streaming e salva blocchi da 5s"""
    buffer = []

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[Recorder] Stato stream: {status}")
        buffer.append(indata.copy())

    block_duration = DURATION  # in secondi
    block_frames = int(FS * block_duration)

    with sd.InputStream(samplerate=FS, device=device_idx, channels=2,
                        dtype='float32', callback=callback, blocksize=1024):
        print("[Recorder] Streaming avviato...")
        while True:
            total_frames = sum(b.shape[0] for b in buffer)
            if total_frames >= block_frames:
                # Accumula abbastanza frame per 5 secondi
                frames_to_write = []
                frames_collected = 0
                while frames_collected < block_frames:
                    block = buffer.pop(0)
                    frames_needed = block_frames - frames_collected
                    if block.shape[0] <= frames_needed:
                        frames_to_write.append(block)
                        frames_collected += block.shape[0]
                    else:
                        frames_to_write.append(block[:frames_needed])
                        buffer.insert(0, block[frames_needed:])
                        frames_collected += frames_needed

                audio_chunk = np.concatenate(frames_to_write, axis=0)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(AUDIO_DIR, f"rec_{timestamp}_stereo.wav")
                sf.write(filename, audio_chunk, FS, subtype='FLOAT')
                print(f"[Recorder] Blocco da 5s salvato: {filename}")
                q.put(filename)

            time.sleep(0.1)  # evita CPU spinning

def fft_highpass_filter_block(data, fs, cutoff=100):
    """Filtro passa-alto FFT su blocco"""
    N = len(data)
    fft_data = np.fft.rfft(data)
    freqs = np.fft.rfftfreq(N, 1/fs)
    mask = freqs > cutoff
    fft_data_filtered = fft_data * mask
    filtered = np.fft.irfft(fft_data_filtered, n=N)
    return filtered.astype(np.float32), fft_data_filtered.real.tolist()  # restituiamo anche lo spettro reale per storico


def noise_reduction_fft(signal_block, noise_profile, reduction_factor=0.5):
    """
    Riduce rumore ambientale sottraendo spettro rumore da segnale
    signal_block, noise_profile: array 1D float32
    reduction_factor: quanto ridurre il rumore (0=no riduzione, 1=massima)
    """
    # FFT segnale e rumore
    fft_signal = np.fft.rfft(signal_block)
    fft_noise = np.fft.rfft(noise_profile)

    # Moduli (magnitudo)
    mag_signal = np.abs(fft_signal)
    mag_noise = np.abs(fft_noise)

    # Fasi
    phase_signal = np.angle(fft_signal)

    # Sottrazione con saturazione a zero (non negativo)
    mag_clean = mag_signal - reduction_factor * mag_noise
    mag_clean = np.clip(mag_clean, 0, None)

    # Ricostruzione spettro complesso con fase originale
    fft_clean = mag_clean * np.exp(1j * phase_signal)

    # Inversa FFT
    clean_signal = np.fft.irfft(fft_clean)

    # Normalizza o mantieni dtype
    return clean_signal.astype(signal_block.dtype)


def process_worker(q, noise_profile):
    """Consuma file WAV, filtra, amplifica e salva gruppi da 10 minuti in OGG"""
    buffer_blocks = []
    block_count = 0
    group_start_time = None

    while True:
        filename = q.get()
        try:
            print(f"[Processor] Elaborazione file: {filename}")
            data, fs = sf.read(filename)
            if data.ndim != 2 or data.shape[1] < 2:
                print("[Processor] File non stereo! Skip")
                continue

            # Estrai canale scelto
            mono = data[:, CHANNEL_TO_KEEP]

            # Riduzione rumore FFT
            filtered = noise_reduction_fft(mono, noise_profile, reduction_factor=0.6)

            # Amplifica
            filtered *= amplify_factor

            # Normalizza per evitare clipping
            max_val = np.max(np.abs(filtered))
            if max_val > 1.0:
                filtered /= max_val

            # Aggiungi blocco al buffer
            buffer_blocks.append(filtered)
            block_count += 1

            # Imposta il tempo iniziale per il nome file del gruppo
            if group_start_time is None:
                group_start_time = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Quando il buffer raggiunge 120 blocchi (10 minuti)
            if block_count == 120:
                print(f"[Processor] Salvando gruppo da 10 minuti: {group_start_time}")
                combined = np.concatenate(buffer_blocks)

                # Salva WAV mono temporaneo del gruppo
                wav_group_path = os.path.join(PROCESSED_DIR, f"group_{group_start_time}_mono.wav")
                sf.write(wav_group_path, combined, fs, subtype='FLOAT')

                # Converti in OGG
                audio_segment = AudioSegment.from_wav(wav_group_path)
                ogg_path = os.path.join(PROCESSED_DIR, f"group_{group_start_time}.ogg")
                audio_segment.export(ogg_path, format="ogg")
                print(f"[Processor] Gruppo da 10 minuti salvato: {ogg_path}")

                # Pulizia temporanei
                os.remove(wav_group_path)

                # Reset buffer
                buffer_blocks = []
                block_count = 0
                group_start_time = None

        except Exception as e:
            print(f"[Processor] Errore durante l'elaborazione: {e}")

        finally:
            q.task_done()
            

def find_device_index(name_substring):
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if name_substring.lower() in dev['name'].lower() and dev['max_input_channels'] >= 2:
            return i
    raise RuntimeError(f"Device audio contenente '{name_substring}' non trovato")

def main():
    device_idx = find_device_index(AUDIODEVICE)
    print(f"Device audio trovato: {device_idx}")

    noise_profile = record_noise_profile(device_idx)

    t1 = threading.Thread(target=record_worker_stream, args=(device_idx, file_queue), daemon=True)
    t2 = threading.Thread(target=process_worker, args=(file_queue,noise_profile,), daemon=True)

    t1.start()
    t2.start()

    print("Threads avviati. Premere Ctrl+C per uscire.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Terminazione richiesta dall'utente.")

if __name__ == "__main__":
    main()
