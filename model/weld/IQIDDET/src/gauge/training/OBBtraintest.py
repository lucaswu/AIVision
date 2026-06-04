#!/usr/bin/env python3
"""Local validation helper for the gauge OBB detector."""

from __future__ import annotations

from ultralytics import YOLO


def main() -> None:
    model = YOLO("yolo26n-obb.pt")
    model.val(data="IQIdata/gauge_obb/data.yaml")


if __name__ == "__main__":
    main()
