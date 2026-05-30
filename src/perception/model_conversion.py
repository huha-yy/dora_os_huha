def convert_to_rknn_from_pt():
    from ultralytics import YOLO

    model = YOLO("yolo11n.pt")
    model.export(
        format="rknn",
        name="rk3588",  # target SoC
        imgsz=640,  # input size (640x640)
    )

def convert_to_rknn():
    from rknn.api import RKNN

    rknn = RKNN()
    print("Configuring RKNN for target RK3588")
    rknn.config(target_platform="rk3588")

    print("Loading ONNX model")
    rknn.load_onnx(model="models/yolov8l.onnx")

    print("Building RKNN model ... this can take a few minutes")
    rknn.build(do_quantization=False)   # or True if you want quantization

    print("Exporting RKNN model")
    rknn.export_rknn("models/yolov8l-rk3588.rknn")

if __name__ == "__main__":
    convert_to_rknn_from_pt()