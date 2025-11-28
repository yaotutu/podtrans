"""检查所有 ASR 模型是否已下载"""

from pathlib import Path


def check_file_size(path: Path) -> str:
    """返回人类可读的文件大小"""
    if not path.exists():
        return "❌ 未找到"

    size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"✅ {size:.1f} {unit}"
        size /= 1024
    return f"✅ {size:.1f} TB"


def main() -> None:
    cache_dir = Path.home() / ".cache"

    print("🔍 PodTrans 模型下载检查\n")
    print("=" * 60)

    # Whisper 模型
    print("\n📦 Whisper 模型:")
    for model in ["tiny", "base", "small", "medium", "large-v2", "large-v3"]:
        path = (
            cache_dir
            / "huggingface"
            / "hub"
            / f"models--Systran--faster-whisper-{model}"
        )
        status = check_file_size(path)
        print(f"  {model:12} {status}")

    # wav2vec2 对齐模型
    print("\n📦 wav2vec2 对齐模型:")
    path = (
        cache_dir
        / "torch"
        / "hub"
        / "checkpoints"
        / "wav2vec2_fairseq_base_ls960_asr_ls960.pth"
    )
    status = "✅ 已下载" if path.exists() else "❌ 未下载"
    size = f" ({path.stat().st_size / 1024 / 1024:.0f} MB)" if path.exists() else ""
    print(f"  wav2vec2:    {status}{size}")

    # 说话人分离模型
    print("\n📦 说话人分离模型:")
    models = [
        ("speechbrain", "models--speechbrain--spkrec-ecapa-voxceleb"),
        ("pyannote-diarization", "models--pyannote--speaker-diarization-3.1"),
        ("pyannote-segmentation", "models--pyannote--segmentation-3.0"),
        ("silero-vad", "snakers4_silero-vad_master"),
    ]

    for name, folder in models:
        if folder.startswith("snakers4"):
            path = cache_dir / "torch" / "hub" / folder
        else:
            path = cache_dir / "huggingface" / "hub" / folder
        status = check_file_size(path)
        print(f"  {name:25} {status}")

    # 总计
    print("\n" + "=" * 60)
    hf_path = cache_dir / "huggingface" / "hub"
    torch_path = cache_dir / "torch" / "hub"

    if hf_path.exists():
        hf_size = check_file_size(hf_path)
        print(f"📊 HuggingFace 缓存总计: {hf_size}")
    else:
        print("📊 HuggingFace 缓存总计: ❌ 目录不存在")

    if torch_path.exists():
        torch_size = check_file_size(torch_path)
        print(f"📊 PyTorch 缓存总计:     {torch_size}")
    else:
        print("📊 PyTorch 缓存总计:     ❌ 目录不存在")

    print("=" * 60)


if __name__ == "__main__":
    main()
