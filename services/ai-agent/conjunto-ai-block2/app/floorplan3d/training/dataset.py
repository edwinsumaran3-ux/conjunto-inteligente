from __future__ import annotations
import os
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset


class FloorPlanDataset(Dataset):
    """CubiCasa-style dataset: images/*.png + masks/*.png with classes 0..4."""

    mean = np.array([0.485, 0.456, 0.406], np.float32)
    std = np.array([0.229, 0.224, 0.225], np.float32)

    def __init__(self, root, size=(512, 512)):
        self.root = root
        self.size = size
        self.files = sorted(
            [
                f
                for f in os.listdir(os.path.join(root, "images"))
                if f.lower().endswith((".png", ".jpg", ".jpeg"))
            ]
        )

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        name = self.files[i]
        img = cv2.imread(os.path.join(self.root, "images", name))
        mask = cv2.imread(
            os.path.join(self.root, "masks", os.path.splitext(name)[0] + ".png"),
            cv2.IMREAD_GRAYSCALE,
        )
        if img is None or mask is None:
            raise FileNotFoundError(name)
        img = cv2.cvtColor(cv2.resize(img, self.size), cv2.COLOR_BGR2RGB)
        mask = cv2.resize(mask, self.size, interpolation=cv2.INTER_NEAREST)
        img = img.astype(np.float32) / 255.0
        img = (img - self.mean) / self.std
        return torch.from_numpy(img.transpose(2, 0, 1)).float(), torch.from_numpy(
            mask
        ).long()
