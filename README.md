# RustRelay Assets

A library of [Rust](https://rust.facepunch.com/) 3D models exported as binary glTF 2.0 (`.glb`),
optimized for web delivery (Draco-compressed geometry + WebP textures).

## Reference use only

These are **low-quality, compressed models intended for reference use only** —
e.g. previews, thumbnails, layout, and tooling. They are not the production
game assets and should not be treated as such. Geometry and textures have been
decimated and compressed for lightweight web delivery, so quality and fidelity
are reduced.

## Structure

```
assets/
├── prefabs/          # Gameplay objects, grouped by category
│   ├── Ammo/         #   40mm grenades, arrows, rifle/shotgun rounds, rockets, torpedoes…
│   ├── Building/     #   doors, walls, gates, ladders, windows
│   ├── Weapons/      #   knives, world models…
│   ├── Clothes/      #   wearables / skins
│   ├── Missions/     #   dungeon & mission props
│   ├── Misc/         #   seasonal & store items
│   └── …
└── bundled/prefabs/  # World / environment content
    ├── autospawn/    #   procedurally spawned clutter & resources (bushes, trees…)
    ├── caves/  radtown/  DeepSea/  world/   # map / biome props
    ├── static/       #   baked static props (e.g. campfire_on)
    ├── fx/  ui/  modding/  system/
    └── …
```

Each `.glb` is a single mesh with its material and texture baked in.

## File format

All files are spec-compliant **glTF 2.0** binaries (exported with glTF-Transform v4.3.0)
using the following extensions:

| Extension                     | Purpose                          |
|-------------------------------|----------------------------------|
| `KHR_draco_mesh_compression`  | Compressed geometry              |
| `EXT_texture_webp`            | WebP textures                    |
| `KHR_lights_punctual`         | Embedded lights                  |
| `EXT_mesh_gpu_instancing`     | Instanced meshes                 |
| `KHR_mesh_quantization`       | Quantized vertex attributes      |
| `EXT_meshopt_compression`     | meshopt-compressed buffers       |
| `KHR_texture_transform`       | UV transforms                    |

> **Important:** because geometry is Draco-compressed and textures are WebP, a loader
> must have the **Draco decoder enabled** (and run in an environment with WebP support,
> i.e. any modern browser). A plain glTF loader without Draco will fail to read geometry.

## Loading in Three.js

```js
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';

// Draco decoder (served from a CDN here; host it yourself in production)
const draco = new DRACOLoader();
draco.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/');

const loader = new GLTFLoader();
loader.setDRACOLoader(draco);

loader.load(
  'assets/prefabs/Weapons/Knife/knife.combat.worldmodel.glb',
  (gltf) => {
    scene.add(gltf.scene);
  },
  undefined,
  (err) => console.error('Failed to load model:', err)
);
```

WebP textures and `KHR_lights_punctual` are handled by `GLTFLoader` automatically.
The few files using `EXT_meshopt_compression` additionally need the meshopt decoder:

```js
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
loader.setMeshoptDecoder(MeshoptDecoder);
```

## Licensing

All assets provided are to be used in accordance with Facepunch's TOS:
[Terms of Service — Facepunch](https://facepunch.com/legal/tos).
