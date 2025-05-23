import os
import subprocess
from datetime import datetime

class DashProcessor:
    def __init__(self, base_dir, processed_folder="processed_audio", archive_folder="archive", segment_duration=600):
        # base_dir: cartella dove si trova lo script
        self.processed_dir = os.path.join(base_dir, processed_folder)
        self.archive_dir = os.path.join(base_dir, archive_folder)
        self.segment_duration = segment_duration  # durata segmento in secondi (es: 600 = 10 minuti)

    def get_folders_to_process(self):
        today = datetime.today().strftime("%Y%m%d")
        folders = []
        if not os.path.isdir(self.processed_dir):
            print(f"Cartella processed_audio non trovata: {self.processed_dir}")
            return folders
        for name in os.listdir(self.processed_dir):
            full_path = os.path.join(self.processed_dir, name)
            if os.path.isdir(full_path) and name.isdigit() and len(name) == 8:
                if name < today:
                    folders.append(full_path)
        folders.sort()
        return folders

    def create_concat_file(self, folder_path):
        files = [f for f in os.listdir(folder_path) if f.lower().endswith(".m4a")]
        files.sort()
        if not files:
            return None
        concat_path = os.path.join(folder_path, "input.txt")
        with open(concat_path, "w") as f:
            for file in files:
                abs_path = os.path.join(folder_path, file).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
        return concat_path, files

    def merge_m4a(self, concat_file, output_file):
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_file
        ]
        print(f"Eseguo merge m4a: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    def create_dash(self, input_file, output_dir, mpd_name):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        mpd_path = os.path.join(output_dir, mpd_name)
        cmd = [
            "ffmpeg", "-y", "-i", input_file,
            "-c", "copy", "-map", "0:a",
            "-f", "dash",
            "-seg_duration", str(self.segment_duration),
            "-use_timeline", "1",
            "-use_template", "1",
            "-adaptation_sets", "id=0,streams=a",
            mpd_path
        ]
        print(f"Eseguo creazione DASH: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        return mpd_path

    def clean_m4a(self, folder_path, files):
        for file in files:
            try:
                os.remove(os.path.join(folder_path, file))
                print(f"Cancellato {file}")
            except Exception as e:
                print(f"Errore cancellando {file}: {e}")

    def run(self):
        folders = self.get_folders_to_process()
        if not folders:
            print("Nessuna cartella da processare.")
            return
        for folder in folders:
            date_folder = os.path.basename(folder)
            print(f"Processo cartella: {folder}")

            concat_result = self.create_concat_file(folder)
            if not concat_result:
                print(f"Nessun file .m4a in {folder}, salto.")
                continue
            concat_file, m4a_files = concat_result

            merged_file = os.path.join(folder, "merged.m4a")
            try:
                self.merge_m4a(concat_file, merged_file)

                # Cartella output: archive/YYYYMMDD/
                archive_output_folder = os.path.join(self.archive_dir, date_folder)
                dash_output_dir = os.path.join(archive_output_folder, "dash_output")
                mpd_name = date_folder + ".mpd"

                self.create_dash(merged_file, dash_output_dir, mpd_name)

                # Sposto il file mpd dalla dash_output a archive/YYYYMMDD (permette che sia allo stesso livello di dash_output)
                mpd_source = os.path.join(dash_output_dir, mpd_name)
                mpd_dest = os.path.join(archive_output_folder, mpd_name)
                if not os.path.exists(archive_output_folder):
                    os.makedirs(archive_output_folder)
                os.rename(mpd_source, mpd_dest)

                # Se tutto ok, pulisco file temporanei
                self.clean_m4a(folder, m4a_files)
                os.remove(concat_file)
                os.remove(merged_file)

                print(f"Processamento cartella {date_folder} completato. MPD in {mpd_dest}")
            except subprocess.CalledProcessError as e:
                print(f"Errore nella elaborazione della cartella {folder}: {e}")

if __name__ == "__main__":
    import sys
    script_dir = os.path.dirname(os.path.abspath(__file__))
    processor = DashProcessor(script_dir)
    processor.run()
