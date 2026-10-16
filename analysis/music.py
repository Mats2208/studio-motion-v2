import librosa, numpy as np, json, sys
y, sr = librosa.load(sys.argv[1], sr=22050, mono=True)
tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time', start_bpm=120)
on = librosa.onset.onset_detect(y=y, sr=sr, units='time', backtrack=False)
rms = librosa.feature.rms(y=y, hop_length=2205)[0]
print("dur", len(y)/sr, "tempo", tempo)
print("beats", np.round(beats,3).tolist())
print("onsets", np.round(on,3).tolist())
print("rms/0.1s dB", np.round(20*np.log10(rms+1e-6),0).astype(int).tolist())
