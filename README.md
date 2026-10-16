# STUDIO MOTION V2

Anuncio 16:9 de 25 s: motion graphics de HyperFrames sobre 8 planos 3D de Blender 5.1 Cycles, sincronizados palabra por palabra con la voz de ElevenLabs.

**Entrega:** `film/renders/studio-motion-v2.mp4`. Voz: **Malena** (ElevenLabs, argentina). También hay versiones con Valeria, Lucía y Maya en `film/renders/studio-motion-v2-<voz>.mp4`; los MP4 no se versionan en git.

## Cambiar la voz sin tocar el 3D

```bash
python tools/eleven.py tts <voice_id> audition/<voz>.mp3 "<guion>" 0.35 0.5 1.0   # requiere ELEVENLABS_API_KEY
python tools/build_voice.py <voz> audition/<voz>.mp3 audition/<voz>.json
```

`build_voice.py` coloca cada frase para que el ataque acústico de su palabra ancla caiga en el instante que renderizó Blender: idea 1.466, vida 6.482, movimiento 8.919, abren 11.304, lugar 15.023 y dimensiones 22.107 s. Después mide sobre la voz ya colocada y corrige hasta que el error baja de 1 frame. Mezcla, renderiza y pega el máster medido en el MP4 (−14 LUFS, ≤ −1.5 dBTP), y al final verifica. Si dos frases se pisaran, falla antes de mezclar.

## Pipeline (cada paso es reproducible desde su script)

| Paso | Comando | Produce |
|---|---|---|
| 1. Tiempos de la voz | `python analysis/whisper_words.py <voz.mp3> analysis/words-source.json` y luego `python tools/build_timeline.py` | `timeline.json`, `film/timeline.js` |
| 2. Mezcla | `python tools/mix_audio.py` (audio fuente en `film/assets/audio/src`, efectos V2 en `film/assets/audio/sfx2`) | `film/assets/audio/mix.wav` (−14 LUFS, ≤ −1 dBTP), `film/peaks.js` |
| 3. Onsets acústicos | `python analysis/whisper_words.py film/assets/audio/mix.wav analysis/words-mix.json` y luego `python tools/onsets.py` | campo `onset` por palabra en `timeline.json` |
| 4. Escenas 3D | en Blender: `import bN_shot; bN_shot.build()` (scripts en `blender/shots/`, librería `blender/lib_sm.py`) | `blender/studio-motion-v2.blend` |
| 5. Render 3D | `python tools/render_queue.py add <escena>` y `python tools/render_queue.py work` | `renders/<escena>/f_####.png` |
| 6. Codificar | `python tools/encode_shots.py` | `film/assets/renders/*.mp4/.webm`, stills, `film/snaps.js` |
| 7. Componer | `cd film && npx hyperframes@0.8.164 check` y luego `render` | MP4 final |
| 8. Verificar | `python tools/verify.py` | `analysis/verification.json`, contact sheet |

Prompt de construcción completo: `prompts/studio-motion-v2.txt`.
