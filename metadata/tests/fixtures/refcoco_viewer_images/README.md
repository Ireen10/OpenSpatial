# RefCOCO viewer fixture images

Placeholder JPEG aligned with `sample.image.path` in the small metadata E2E sample:

- `type7/train2014/COCO_train2014_000000569667.jpg` — 640×426, solid color (for `openspatial-metadata-viz` only).

Regenerate (from repo root, with Pillow):

```bash
python -c "from pathlib import Path; from PIL import Image; p=Path('metadata/tests/fixtures/refcoco_viewer_images/type7/train2014'); p.mkdir(parents=True, exist_ok=True); Image.new('RGB',(640,426),(55,90,140)).save(p/'COCO_train2014_000000569667.jpg','JPEG',quality=88)"
```
