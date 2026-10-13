# Blower scroll scene

The approved white/cobalt product story is implemented in `static/js/blower-scene.js` as an original Three.js assembly. It is a browser enhancement of the Python/Jinja page, with native scrolling. No React, GSAP, scroll interceptor, external asset service or analytics is involved.

## Integration

```html
<section data-blower-section>
  <div class="blower-stage">
    <!-- Accessible product description and all calls to action remain in HTML. -->
    <img data-blower-poster src="…" alt="Воздуходувка AERZEN">
    <canvas data-blower-canvas aria-hidden="true"></canvas>
    <button type="button" data-motion-toggle aria-pressed="false">Статичный вид</button>
  </div>
</section>
```

```js
import { initBlowerScene } from "/static/js/blower-scene.js";
const blowerMotion = initBlowerScene({
  canvas: "[data-blower-canvas]",
  section: "[data-blower-section]",
  poster: "[data-blower-poster]",
  onProgress(progress, { phase, explosion, mobile }) {
    // Optional short HTML stage labels; never move or disable the primary CTA.
  },
});
```

The stage should have stable reserved dimensions. Poster and canvas overlap; set the canvas to `pointer-events: none`, `opacity: 0` initially, and give both the same area. On desktop the section may be about 240–280vh with the stage sticky at the viewport top. On widths <=767px use a normal-flow stage and a short section. With reduced motion, also remove the tall sticky CSS section so users are not asked to scroll through an empty story. The script does not inject page structure or heights.

The scene sets `data-motion-ready="true"`, `data-motion-state`, `data-motion-active`, `--assembly-progress`, and `--assembly-explosion` on its section. `blower:progress` is emitted locally with `{progress, phase, explosion, mobile}`. The provided toggle switches to the poster and back; its label, disabled state and `aria-pressed` are managed by the scene. Its focus appearance belongs to the page CSS.

The returned controller has `ready` (promise resolving true when initialized), `setStatic(boolean)`, `refresh()`, `getState()`, and `destroy()`. `setProgress(number|null)` is for deterministic visual QA or an explicitly wired alternative control; null returns to native scroll progress. `destroy()` cancels animation frames, removes listeners/observers, disposes geometries/materials/environment/WebGL resources and restores the poster.

## Choreography

| Native desktop progress | State |
| --- | --- |
| 0–0.13 | High fidelity poster crossfades into the original 3D assembly |
| 0.045–0.255 | Product rotates from three-quarter to straight side-on |
| 0.25–0.56 | Intake, cover, hollow ribbed casing, silver twin helical rotors, rear cover, coupling and finned motor separate along a horizontal X axis |
| 0.56–0.71 | Exploded rest; base stays fixed and level |
| 0.71–0.94 | Parts reassemble along the same axis |
| 0.94–1 | Assembled rest and exit into normal content |

The orthographic camera widens while the assembly opens. There is no camera roll or diagonal exploded arrangement. Reverse scrolling reverses the same transforms. Motion is keyed to user input; there is no continuous ambient spinning. A short damped finish follows scroll updates, then the render loop stops. Rendering also stops offscreen and when the document is hidden.

On mobile, separation and rotation are reduced; progress uses ordinary entry/exit through the short section. At reduced motion the library is not loaded and the static poster remains. Missing module, failed WebGL initialization or context loss restores that same poster. HTML links/forms never depend on the canvas.

## Fidelity and rights

This original geometry is a **product illustration**, not certified AERZEN CAD or a service drawing. Geometry is mechanically plausible but the rotor/casing arrangement and proportions have not been validated against a particular supplier model. Do not publish it as a claim about the exact product's internal construction. The accurate product poster can be replaced independently; authorized supplier CAD would be the right upgrade when exact dimensional/internals fidelity is needed.

Three.js 0.186.1 was verified and downloaded on 2026-10-12 from the official npm package linked to `mrdoob/three.js`. The npm tarball's SHA-512 SRI was checked before extracting the two required original build modules and the license. It is self-hosted under `static/vendor/three/`; no CDN, new package manager or runtime account is required.

- Official documentation: https://threejs.org/docs/
- Official project/license: https://github.com/mrdoob/three.js/blob/dev/LICENSE
- Version metadata: https://registry.npmjs.org/three/0.186.1
- Exact package: https://registry.npmjs.org/three/-/three-0.186.1.tgz
- MIT license retained: `static/vendor/three/LICENSE`
- Integrity and individual SHA-256 values: `static/vendor/three/provenance.json`

No paid access is needed; the MIT copyright/license notice must remain with the distribution. Do not label supplier photos/CAD as covered by the Three.js license.

## Budget and verification

Original module sizes: `three.module.js` 662,772 bytes and `three.core.js` 1,458,113 bytes; gzip level 9 measured at 130,785 and 286,503 bytes (417,288 bytes total). Enable normal HTTP gzip/Brotli and caching. The modules are lazily imported near the section; reduced motion doesn't download them. Pixel ratio is bounded at 1.65 desktop/1.25 mobile and shadows at 1024px.

An isolated Chromium harness was visually checked at 1440×900 and 390×844. Rotation, full horizontal explosion, reassembly, reversed progress, static control, reduced-motion preference, and blocked-vendor fallback were exercised without uncaught page errors. Screenshots were inspected. A desktop `setProgress(0.63)` run settled at the exact target and produced zero new frames during a subsequent 500ms check. Mobile and reduced-motion checks likewise had zero animation frames once settled. This is an input-driven render loop, not an idle loop.

Same-material geometry is merged within each movable part; the measured exploded frame reported 67 rendering calls, 104,266 triangles, 34 geometries and 4 renderer textures (including environment/shadow resources). The headless software renderer is slower than a target-device GPU, so no unmeasured frame-rate guarantee is made. Integrated page proportions, poster crossfade, native scrolling, sticky exit, keyboard focus, GPU responsiveness and the final public URL still require verification in the complete site.
