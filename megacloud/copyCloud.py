import os
import shutil
import pathlib
import subprocess
from datetime import datetime
import traceback



class HLSCopyCloud:

    BASEDIR = "/aurigalab/python/infinity_recorder"

    PROCESSED_AUDIO_DIR = os.path.join(BASEDIR, "processed_audio")

    CLOUD_DIR = "/aurigalab/megacloud/iRec"

    subFolders = []

    today = None 




    def __init__(self):
        try:
            self.today = datetime.now().strftime("%Y%m%d")
            self.subFolders = [ f.path for f in os.scandir(self.PROCESSED_AUDIO_DIR) if f.is_dir() ]
            self.checkValidFolders()
        except:
            print(traceback.format_exc())





    def checkValidFolders(self):
        for d in self.subFolders:
            audioPath = pathlib.PurePath(d)
            folderName = audioPath.name
            if(folderName != self.today):

                cloudFolderPath = os.path.join(self.CLOUD_DIR, folderName)
                if os.path.exists(cloudFolderPath):
                    print(f"Preparing {cloudFolderPath} ...")
                    shutil.rmtree(cloudFolderPath)
                os.mkdir(cloudFolderPath)

                try:
                    print(f"Rempapping {d} ...")
                    self.reWrappingAudioFolder(audioPath, folderName)

                    print(f"Copying HLS {folderName} to Cloud ...")
                    shutil.copytree(d, cloudFolderPath, dirs_exist_ok=True)
                    print(f"Removing {d} ...")
                    shutil.rmtree(d)
                except:
                    print(f"Error on copy {d} on {cloudFolderPath}")
                    print(traceback.format_exc())
            else:
                print(f"Folder {d} is not processable, continue...")






    def reWrappingAudioFolder(self, audioFolder, folderName):
        audioFolderPath = pathlib.Path(audioFolder)
        files = sorted(audioFolderPath.glob("*.m4a"))
        segmentPath = os.path.join(audioFolder, "segments")
        if not os.path.exists(segmentPath):
            os.mkdir(segmentPath)

        print("Creation list file input.txt...")
        inputTXTPath = os.path.join(audioFolder, "input.txt")
        with open(inputTXTPath, "w", encoding="utf-8") as f:
            for filename in files:
                f.write(f"file '{filename.name}'\n")

        print("Joining m4a files...")
        joinFileName = "output.m4a"
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", "input.txt",
            "-c", "copy",
            joinFileName
        ]
        result = subprocess.run(cmd, cwd=audioFolder, capture_output=True, text=True)

        print(f"Preparing Segments Path ...")
        segmentPath = os.path.join(audioFolder, "segments")
        if os.path.exists(segmentPath):
            shutil.rmtree(segmentPath)
        os.mkdir(segmentPath)

        print("Creating Streaming HLS...")
        cmd = [
            "ffmpeg",
            "-i", "output.m4a",
            "-c", "copy",
            "-hls_time", "600",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", "segments/chunk-%03d.ts",
            f"{folderName}.m3u8"
        ]
        result = subprocess.run(cmd, cwd=audioFolder, capture_output=True, text=True)
        
        self.regenerateM3u8(audioFolder, folderName)
        self.cleanGarbage(audioFolder)




    def cleanGarbage(self, audioFolder):
        # audioFolderPath = pathlib.Path(audioFolder)

        '''
        for filename in audioFolderPath.glob(f"*.m4a"):
            try:
                filename.unlink()
            except:
                print(f"File {filename} not removed, you should remove it manually.")
        '''

        inputTXTPath = os.path.join(audioFolder, "input.txt")
        if os.path.exists(inputTXTPath):
            try:
                pathlib.Path(inputTXTPath).unlink()
            except:
                print(f"File {inputTXTPath} not removed.")




    def regenerateM3u8(self, audioFolder, folderName):
        m3u8Path = os.path.join(audioFolder, f"{folderName}.m3u8")

        with open(m3u8Path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        with open(m3u8Path, "w", encoding="utf-8") as f:
            for line in lines:
                # Se la riga NON è un commento e contiene "chunk-", aggiungi "segments/" davanti
                if not line.startswith("#") and "chunk-" in line and not line.startswith("segments/"):
                    line = "segments/" + line
                f.write(line)            


foo = HLSCopyCloud()