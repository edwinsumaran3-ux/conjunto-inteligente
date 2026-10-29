from __future__ import annotations
import torch
import torch.nn as nn


class DoubleConv(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(cin, cout, 3, padding=1, bias=False),
            nn.BatchNorm2d(cout),
            nn.ReLU(inplace=True),
            nn.Conv2d(cout, cout, 3, padding=1, bias=False),
            nn.BatchNorm2d(cout),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class UNet(nn.Module):
    def __init__(self, in_channels=3, n_classes=5, base=32):
        super().__init__()
        self.pool = nn.MaxPool2d(2)
        self.d1 = DoubleConv(in_channels, base)
        self.d2 = DoubleConv(base, base * 2)
        self.d3 = DoubleConv(base * 2, base * 4)
        self.d4 = DoubleConv(base * 4, base * 8)
        self.b = DoubleConv(base * 8, base * 16)
        self.u4 = DoubleConv(base * 16, base * 8)
        self.u3 = DoubleConv(base * 8, base * 4)
        self.u2 = DoubleConv(base * 4, base * 2)
        self.u1 = DoubleConv(base * 2, base)
        self.t4 = nn.ConvTranspose2d(base * 16, base * 8, 2, 2)
        self.t3 = nn.ConvTranspose2d(base * 8, base * 4, 2, 2)
        self.t2 = nn.ConvTranspose2d(base * 4, base * 2, 2, 2)
        self.t1 = nn.ConvTranspose2d(base * 2, base, 2, 2)
        self.out = nn.Conv2d(base, n_classes, 1)

    def forward(self, x):
        c1 = self.d1(x)
        c2 = self.d2(self.pool(c1))
        c3 = self.d3(self.pool(c2))
        c4 = self.d4(self.pool(c3))
        b = self.b(self.pool(c4))
        x = self.u4(torch.cat([self.t4(b), c4], 1))
        x = self.u3(torch.cat([self.t3(x), c3], 1))
        x = self.u2(torch.cat([self.t2(x), c2], 1))
        x = self.u1(torch.cat([self.t1(x), c1], 1))
        return self.out(x)
