"""预下载所有 ASR 模型

这个脚本会下载 Whisper 模型到本地缓存,避免首次运行时等待。
其他模型 (wav2vec2, pyannote) 会在首次使用时自动下载。
"""

from podtrans.asr import WhisperXHandler
from podtrans.config import get_settings


def main() -> None:
    settings = get_settings()

    print("🎯 开始预下载 ASR 模型...")
    print(f"📦 Whisper 模型: {settings.whisper_model}")
    print(f"💾 设备: {settings.device}")
    print(f"🔧 计算类型: {settings.compute_type}")
    print()

    # 初始化 WhisperXHandler (会触发 Whisper 模型下载)
    print("1️⃣ 下载 Whisper 模型...")
    handler = WhisperXHandler(
        model_name=settings.whisper_model,
        device=settings.device,
        compute_type=settings.compute_type,
    )
    handler.load_model()
    print("✅ Whisper 模型下载完成!\n")

    print("2️⃣ wav2vec2 对齐模型会在首次运行 align() 时自动下载")
    print("3️⃣ 说话人分离模型会在首次运行 diarize() 时自动下载 (需要 HF_TOKEN)")
    print()
    print("🎉 主要模型预下载完成!")
    print("💡 提示: 运行一次 `podtrans transcribe` 命令会自动下载所有剩余模型")


if __name__ == "__main__":
    main()
