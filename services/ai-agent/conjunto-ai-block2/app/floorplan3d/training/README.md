# Entrenamiento del motor neuronal

Estructura esperada:

```text
data/
  images/*.png
  masks/*.png   # uint8: 0 background, 1 wall, 2 door, 3 window, 4 room
```

El pipeline es compatible con datasets de planos anotados como CubiCasa5K. Para producción se recomienda separar por proyecto/edificio para evitar fuga de estilos entre train y validation.

```bash
python -m app.floorplan3d.training.train
python -m app.floorplan3d.training.export_onnx
```

Luego define `FLOORPLAN_ENGINE=neural` y `ONNX_MODEL_PATH=/models/floorplan_unet.onnx`.
