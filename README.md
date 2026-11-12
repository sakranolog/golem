# הגולם · The Too-Literal Golem

A small 3D browser game that teaches kids (ages 8–11) to think like programmers. You give a clay golem instructions with stones, and it does exactly, but exactly, what you said. Five short daily puzzles, in Hebrew, with a narrator.

Built in a day as an experiment.

## Run it

```bash
npm install
npm run dev
```

Then open the address Vite prints. Add `?dev=1` to unlock all five days and show a "solve" button for testing.

## ElevenLabs API key

All voice, music and sound effects were generated with [ElevenLabs](https://elevenlabs.io). The generated files are already in `public/audio`, so **the game runs without a key**.

You only need a key to regenerate or change the audio. Create a `.env` file in the project root:

```
ELEVENLABS_API_KEY=your_key_here
```

Then:

```bash
npm run audio                                  # generate anything missing
node tools/gen-audio.mjs --force --only vo_intro   # redo one clip
```

The lines, prompts and voice are defined in `tools/audio-spec.mjs`. `.env` is git-ignored; never commit your key.

## 3D assets

The golem, props and workshop are built by Python scripts in `blender/` and exported to `public/models`. The exported files are in the repo, so Blender is only needed if you want to rebuild them:

```bash
npm run assets
```

## Stack

Vite, three.js, the `postprocessing` library, Blender (headless) for models and baked lighting, ElevenLabs for audio.
