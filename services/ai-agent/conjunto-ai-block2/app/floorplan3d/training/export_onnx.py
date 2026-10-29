import torch
from .model_unet import UNet

model = UNet()
model.load_state_dict(torch.load("floorplan_unet_best.pt", map_location="cpu"))
model.eval()
torch.onnx.export(
    model,
    torch.zeros(1, 3, 512, 512),
    "floorplan_unet.onnx",
    input_names=["input"],
    output_names=["logits"],
    opset_version=17,
    dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
)
print("floorplan_unet.onnx listo")
