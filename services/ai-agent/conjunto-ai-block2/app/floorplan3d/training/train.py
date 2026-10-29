from __future__ import annotations
import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from .dataset import FloorPlanDataset
from .model_unet import UNet


def main():
    root = os.getenv("DATA_ROOT", "./data")
    epochs = int(os.getenv("EPOCHS", "60"))
    batch = int(os.getenv("BATCH", "8"))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    ds = FloorPlanDataset(root)
    nval = max(1, int(len(ds) * 0.15))
    train, val = random_split(
        ds, [len(ds) - nval, nval], generator=torch.Generator().manual_seed(42)
    )
    tl = DataLoader(train, batch_size=batch, shuffle=True, num_workers=2)
    vl = DataLoader(val, batch_size=batch, num_workers=1)
    model = UNet().to(device)
    opt = torch.optim.AdamW(
        model.parameters(), lr=float(os.getenv("LR", "1e-3")), weight_decay=1e-4
    )
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    loss_fn = nn.CrossEntropyLoss(
        weight=torch.tensor([0.5, 1, 4, 4, 1.5], device=device)
    )
    best = 1e9
    for ep in range(1, epochs + 1):
        model.train()
        total = 0
        for x, y in tl:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()
            total += loss.item() * x.size(0)
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for x, y in vl:
                val_loss += loss_fn(model(x.to(device)), y.to(device)).item() * x.size(
                    0
                )
        val_loss /= max(1, len(val))
        sched.step()
        print(f"epoch={ep:03d} train={total/max(1,len(train)):.4f} val={val_loss:.4f}")
        if val_loss < best:
            best = val_loss
            torch.save(model.state_dict(), "floorplan_unet_best.pt")


if __name__ == "__main__":
    main()
