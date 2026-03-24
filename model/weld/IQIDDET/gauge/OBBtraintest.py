from ultralytics import YOLO

# Load a model
model = YOLO("yolo26n-obb.pt")

# Validate the model
metrics = model.val(data="IQIdata/gauge_obb/data.yaml")