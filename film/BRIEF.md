---
workflow: general-video
flow: automation
storyboard: no
message: "Del primer trazo a producción completa: STUDIO enseña a crear en todas las dimensiones."
destination: web / redes 16:9
aspect: "16:9"
language: es-419
length: 25s
audience: creativos que quieren pasar de tutoriales a producción real (3D, motion, diseño, sonido)
---

## Intent

Rehacer desde cero el anuncio STUDIO MOTION que se había producido en Codex, con más rigor y un look cinematográfico y moderno. Es un híbrido: motion graphics de calidad (tipografía cinética sincronizada a la voz, UI de producto, guías, retículas) y renders 3D de Blender hechos desde cero. Comunica lo mismo que el guion existente, sin copiar el video anterior.

## Assets

- Voz final: **Malena** (ElevenLabs, argentina, joven, dinámica), elegida entre 3 audiciones (`audition/`). La voz original "Maya", la música y los efectos de la producción anterior están en `film/assets/audio/src`. Los efectos de V2 (sin campanas) están en `film/assets/audio/sfx2`.
- Guion, en 6 frases: "Todo empieza con una idea." / "La imaginás, la probás… y le das vida." / "Un trazo se transforma en movimiento." / "Las preguntas abren nuevas posibilidades." / "Y cada pieza encuentra su lugar." / "Creá en todas las dimensiones."

## Customizations

- Timing: Whisper (faster-whisper medium) cruzado con el alineamiento de ElevenLabs, más el onset acústico medido en la voz ya colocada → `timeline.json`.
- 3D: 8 planos de Blender 5.1 Cycles construidos en vivo vía MCP en el Blender del usuario y renderizados en background.
- Spec completo: `../prompts/studio-motion-v2.txt`.
